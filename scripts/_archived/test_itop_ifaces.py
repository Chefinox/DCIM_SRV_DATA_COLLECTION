import sys
sys.path.append('/home/infra/dcim_metrics_project/scripts')
from dcim_itop_unified_consumer import ITopClient
itop = ITopClient()
body = itop._post({
    "operation": "core/get", "class": "PhysicalInterface",
    "key": "SELECT PhysicalInterface WHERE connectableci_id_friendlyname LIKE 'FIT-Core-RTR%'",
    "output_fields": "name,connectableci_id_friendlyname"
})
if body and body.get("objects"):
    print("Found interfaces for FIT-Core-RTR:")
    for obj_id, obj in body["objects"].items():
        print(" -", obj["fields"]["name"])
else:
    print("No interfaces found.")
