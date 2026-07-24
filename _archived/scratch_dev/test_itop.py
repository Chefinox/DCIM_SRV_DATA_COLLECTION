import sys
sys.path.append("/home/infra/dcim_metrics_project")
from scripts.itop_to_cache_sync import itop_get
import json
print(json.dumps(itop_get("Server", "name,serialnumber", 1), indent=2))
