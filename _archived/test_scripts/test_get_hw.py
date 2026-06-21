import sys
import logging
sys.path.append('/home/infra/dcim_metrics_project/scripts')
from itop_sync_utils import get_server_hardware
logging.basicConfig(level=logging.DEBUG)
print("Calling get_server_hardware...")
try:
    res = get_server_hardware("SRV-Render-01")
    print("Done:", res)
except Exception as e:
    print("Error:", e)
