import sys
sys.path.append('/home/infra/dcim_metrics_project/scripts')
from dcim_itop_unified_consumer import ITopClient
itop = ITopClient()
body = itop._post({
    "operation": "core/get", "class": "NetworkDevice",
    "key": "SELECT NetworkDevice WHERE name='FIT-Core-RTR'",
    "output_fields": "name,location_id,location_name"
})
if body and body.get("objects"):
    for obj_id, obj in body["objects"].items():
        print(f"Device: {obj['fields']['name']}")
        print(f"Location ID: {obj['fields']['location_id']}")
        print(f"Location Name: {obj['fields'].get('location_name', 'N/A')}")
