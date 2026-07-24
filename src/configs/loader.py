import os
import logging
import sys

def read_secret(name: str, fallback: str = None) -> str:
    """Reads a secret from Vault, Docker secrets, or environment variables."""
    # Strict rule: No fallback for passwords to prevent accidental production leaks
    if "PASS" in name.upper() or "PASSWORD" in name.upper():
        fallback = None
        
    try:
        from src.utils.secrets import get_secret
        val = get_secret(name.lower())
        if val:
            return val
    except Exception as e:
        logging.warning(f"Failed to use get_secret for {name}: {e}")

    # Final fallback if Vault fails
    return os.getenv(name, fallback)

