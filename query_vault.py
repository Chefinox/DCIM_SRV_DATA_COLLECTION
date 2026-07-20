import sys
sys.path.append('/home/infra/dcim_metrics_project')
from src.utils.secrets import get_secret
print("postgres password:", get_secret("postgres", "password"))
print("ai_team password:", get_secret("ai_team", "password"))
