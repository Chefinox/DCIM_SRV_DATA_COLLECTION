import sys
import os
import requests
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import dcim_inventory_poller

try:
    res = dcim_inventory_poller.poll_server("10.50.0.2")
    import json
    print(json.dumps(res, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
