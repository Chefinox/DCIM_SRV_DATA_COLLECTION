import os
import hvac

def get_secret(name: str, fallback_env: str = None) -> str:
    """Read secret from HashiCorp Vault, fallback to env var."""
    
    vault_addr = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
    role_id_path = os.environ.get('VAULT_ROLE_ID_PATH', '/home/infra/dcim_metrics_project/vault/config/role_id')
    secret_id_path = os.environ.get('VAULT_SECRET_ID_PATH', '/home/infra/dcim_metrics_project/vault/config/secret_id')
    
    try:
        # Check if role_id and secret_id exist
        if os.path.exists(role_id_path) and os.path.exists(secret_id_path):
            with open(role_id_path, 'r') as f:
                role_id = f.read().strip()
            with open(secret_id_path, 'r') as f:
                secret_id = f.read().strip()
            
            client = hvac.Client(url=vault_addr)
            
            # Authenticate with AppRole
            client.auth.approle.login(
                role_id=role_id,
                secret_id=secret_id
            )
            
            # Read secret from Vault (kv-v2)
            # We map the docker secret name to the vault key name
            vault_key_map = {
                'sot_db_pass': 'postgres',
                'ralph_api_token': 'ralph',
                'ralph_api_token_new': 'ralph_new'
            }
            
            vault_key = vault_key_map.get(name, name)
            
            read_response = client.secrets.kv.v2.read_secret_version(
                mount_point='secret',
                path=f'dcim/{vault_key}'
            )
            
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
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, 'r') as f:
            return f.read().strip()
    
    if fallback_env:
        return os.environ.get(fallback_env, "")
        
    return os.environ.get(name, "")
