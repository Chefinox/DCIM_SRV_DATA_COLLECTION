import os
import logging

def read_secret(name: str, fallback: str = None) -> str:
    """Reads a secret from /run/secrets or environment variables."""
    # Strict rule: No fallback for passwords to prevent accidental production leaks
    if "PASS" in name.upper() or "PASSWORD" in name.upper():
        fallback = None

    secret_path = f"/run/secrets/dcim/{name.lower()}"
    try:
        if os.path.exists(secret_path):
            with open(secret_path) as f:
                return f.read().strip()
    except Exception as e:
        logging.warning(f"Could not read secret file {secret_path}: {e}")

    return os.getenv(name, fallback)
