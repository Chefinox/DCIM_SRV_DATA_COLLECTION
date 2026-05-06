from .loader import read_secret

def get_db_config() -> dict:
    """
    Returns database configuration with lazy loading.
    Mandatory secrets like SOT_DB_PASS will return None if not set,
    forcing the DB client to fail fast rather than using an unsafe default.
    """
    return {
        "host":     read_secret("SOT_DB_HOST", "192.168.101.73"),
        "dbname":   read_secret("SOT_DB_NAME", "dcim_sot"),
        "user":     read_secret("SOT_DB_USER", "sot_admin"),
        "password": read_secret("SOT_DB_PASS") # Mandatory, no default fallback
    }
