import os
import json
import time
import logging
import hvac

logger = logging.getLogger(__name__)

# Map secret names to their scoped AppRole connector suffix.
# Each connector has its own role_id/secret_id files at:
#   vault/config/role_id_<connector>  and  vault/config/secret_id_<connector>
# Fallback: use the generic role_id/secret_id if per-connector files not found.
_SECRET_TO_CONNECTOR = {
    'elastic_pass': 'elasticsearch',
    'kibana_pass': 'elasticsearch',
    'postgres': 'postgres',
    'sot_db_pass': 'postgres',
    'redfish_pass': 'redfish',
    'ralph': 'ralph',
    'ralph_new': 'ralph',
    'ralph_api_token': 'ralph',
    'ralph_api_token_new': 'ralph',
}

# In-memory token cache: connector_key -> {"token": str, "expires_at": float}
_token_cache: dict = {}

# Buffer in seconds before actual TTL expiry to trigger refresh early.
_EXPIRY_BUFFER_SECONDS = 60

# Default token_ttl assumed if Vault doesn't report lease_duration.
_DEFAULT_TTL_SECONDS = 3600


def _cache_dir() -> str | None:
    """Return the directory for file-based token cache with restrictive permissions (0o700).

    Logs an explicit WARNING if the base directory is missing or uncreatable.
    """
    base = os.environ.get(
        'VAULT_CONFIG_DIR',
        '/home/infra/dcim_metrics_project/vault/config'
    )
    if not os.path.exists(base):
        logger.warning(
            "vault: base config directory '%s' does not exist; file-based token caching disabled.",
            base
        )
        return None

    d = os.path.join(base, 'cache')
    try:
        os.makedirs(d, mode=0o700, exist_ok=True)
        os.chmod(d, 0o700)
        return d
    except OSError as exc:
        logger.warning(
            "vault: failed to create cache directory '%s': %s; file-based token caching disabled.",
            d, exc
        )
        return None


def _cache_file_path(connector_key: str) -> str | None:
    """Return the file path for a connector's cached token, or None if cache dir unavailable."""
    d = _cache_dir()
    if not d:
        return None
    return os.path.join(d, f'token_{connector_key}.json')


def _read_cached_token(connector_key: str) -> str | None:
    """Read a valid cached token (in-memory first, then file).

    Returns the token string if still valid, or None.
    """
    now = time.time()

    # 1. Try in-memory cache
    entry = _token_cache.get(connector_key)
    if entry and entry['expires_at'] - _EXPIRY_BUFFER_SECONDS > now:
        logger.debug("vault: reusing in-memory cached token for '%s'", connector_key)
        return entry['token']

    # 2. Try file cache (useful when process was restarted but token is still valid)
    cache_file = _cache_file_path(connector_key)
    if not cache_file:
        return None

    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                data = json.load(f)
            if data.get('expires_at', 0) - _EXPIRY_BUFFER_SECONDS > now:
                token = data['token']
                # Populate in-memory cache from file
                _token_cache[connector_key] = {
                    'token': token,
                    'expires_at': data['expires_at'],
                }
                logger.debug("vault: reusing file-cached token for '%s'", connector_key)
                return token
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        logger.debug("vault: ignoring corrupt cache file for '%s': %s", connector_key, exc)

    return None


def _store_cached_token(connector_key: str, token: str, lease_duration: int) -> None:
    """Store token in both in-memory and file cache (file permissions 0o600)."""
    ttl = lease_duration if lease_duration > 0 else _DEFAULT_TTL_SECONDS
    expires_at = time.time() + ttl

    # In-memory
    _token_cache[connector_key] = {
        'token': token,
        'expires_at': expires_at,
    }

    # File (for cross-process / restart reuse)
    cache_file = _cache_file_path(connector_key)
    if not cache_file:
        return

    try:
        with open(cache_file, 'w') as f:
            json.dump({'token': token, 'expires_at': expires_at}, f)
        os.chmod(cache_file, 0o600)
    except OSError as exc:
        logger.warning("vault: failed to write or set permissions on cache file for '%s': %s", connector_key, exc)


def _resolve_approle_paths(name: str):
    """Resolve role_id and secret_id file paths for a given secret name.
    
    Uses per-connector AppRole if available, falls back to generic dcim-role.
    """
    base_dir = os.environ.get(
        'VAULT_CONFIG_DIR',
        '/home/infra/dcim_metrics_project/vault/config'
    )
    connector = _SECRET_TO_CONNECTOR.get(name)
    
    if connector:
        scoped_role = os.path.join(base_dir, f'role_id_{connector}')
        scoped_secret = os.path.join(base_dir, f'secret_id_{connector}')
        if os.path.exists(scoped_role) and os.path.exists(scoped_secret):
            return scoped_role, scoped_secret
    
    # Fallback to generic (legacy dcim-role) or env-overridden paths
    role_id_path = os.environ.get('VAULT_ROLE_ID_PATH', os.path.join(base_dir, 'role_id'))
    secret_id_path = os.environ.get('VAULT_SECRET_ID_PATH', os.path.join(base_dir, 'secret_id'))
    return role_id_path, secret_id_path


def _invalidate_cache(connector_key: str) -> None:
    """Remove cached token from both in-memory and file cache."""
    _token_cache.pop(connector_key, None)
    cache_file = _cache_file_path(connector_key)
    if cache_file:
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
        except OSError:
            pass


def _login_fresh(client, role_id_path: str, secret_id_path: str, connector: str):
    """Perform fresh AppRole login and cache the resulting token."""
    with open(role_id_path, 'r') as f:
        role_id = f.read().strip()
    with open(secret_id_path, 'r') as f:
        secret_id = f.read().strip()

    login_resp = client.auth.approle.login(
        role_id=role_id,
        secret_id=secret_id
    )

    new_token = login_resp['auth']['client_token']
    lease_duration = login_resp['auth'].get('lease_duration', _DEFAULT_TTL_SECONDS)
    _store_cached_token(connector, new_token, lease_duration)
    logger.debug("vault: fresh login for connector '%s' (ttl=%ds)", connector, lease_duration)


def get_secret(name: str, fallback_env: str = None) -> str:
    """Read secret from HashiCorp Vault, fallback to env var.

    Token caching: reuses Vault AppRole tokens across calls to avoid
    creating a new lease on every invocation. Supports both in-memory
    (long-running processes) and file-based (cross-process) caching.
    If a cached token is rejected (403), it is invalidated and a fresh
    login is attempted once before falling back.
    """
    
    vault_addr = os.environ.get('VAULT_ADDR', 'http://10.70.0.56:8200')
    role_id_path, secret_id_path = _resolve_approle_paths(name)
    
    try:
        # Check if role_id and secret_id exist
        if os.path.exists(role_id_path) and os.path.exists(secret_id_path):
            # Determine connector key for caching
            connector = _SECRET_TO_CONNECTOR.get(name, 'generic')
            
            # Try to reuse a cached token first
            cached_token = _read_cached_token(connector)
            
            client = hvac.Client(url=vault_addr)
            
            if cached_token:
                # Reuse cached token — no new login / lease
                client.token = cached_token
            else:
                # No valid cached token — perform fresh AppRole login
                _login_fresh(client, role_id_path, secret_id_path, connector)
            
            # Read secret from Vault (kv-v2)
            # We map the docker secret name to the vault key name
            vault_key_map = {
                'sot_db_pass': 'postgres',
                'ralph_api_token': 'ralph',
                'ralph_api_token_new': 'ralph_new'
            }
            
            vault_key = vault_key_map.get(name, name)
            
            try:
                read_response = client.secrets.kv.v2.read_secret_version(
                    mount_point='secret',
                    path=f'dcim/{vault_key}'
                )
            except hvac.exceptions.Forbidden:
                # Cached token was revoked or expired server-side — retry once
                if cached_token:
                    logger.debug("vault: cached token rejected (403) for '%s', re-login", connector)
                    _invalidate_cache(connector)
                    _login_fresh(client, role_id_path, secret_id_path, connector)
                    read_response = client.secrets.kv.v2.read_secret_version(
                        mount_point='secret',
                        path=f'dcim/{vault_key}'
                    )
                else:
                    raise
            
            # Extract the actual value
            # The structure we put was e.g. `vault kv put secret/dcim/postgres password='...'`
            # For ralph it was `token='...'`
            secret_data = read_response['data']['data']
            if 'password' in secret_data:
                return secret_data['password']
            elif 'token' in secret_data:
                return secret_data['token']
            else:
                # return the first value if we don't know the key
                return list(secret_data.values())[0]
                
    except Exception as e:
        print(f"Failed to read secret '{name}' from Vault: {e}")
        pass

    # Fallback to Docker secret or Env Var
    secret_path = f"/run/secrets/dcim/{name}"
    if not os.path.exists(secret_path):
        secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, 'r') as f:
            return f.read().strip()
    
    if fallback_env:
        return os.environ.get(fallback_env, "")
        
    return os.environ.get(name, "")
