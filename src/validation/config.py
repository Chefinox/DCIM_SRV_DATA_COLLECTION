import yaml
import os

def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r') as f:
        try:
            return yaml.safe_load(f) or {}
        except Exception:
            return {}
