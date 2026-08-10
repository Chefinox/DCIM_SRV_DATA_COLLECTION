import yaml
import os

CONFIG_PATH = os.environ.get("VALIDATION_CONFIG_PATH", "/home/infra/dcim_metrics_project/configs/validation_rules.yaml")

def load_validation_config():
    """Load validation rules configuration."""
    if not os.path.exists(CONFIG_PATH):
        # Default safe configuration
        return {
            "range": {"enabled": False},
            "format": {"enabled": False},
            "freshness": {"enabled": False},
            "source_allowlist": {"enabled": False},
            "deduplication": {"enabled": False}
        }
        
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
            return config.get("rules", {})
    except Exception as e:
        print(f"Error loading validation config: {e}")
        return {}
