import sys
import psycopg2
sys.path.append('/home/infra/dcim_metrics_project/scripts')
from dcim_itop_unified_consumer import ITopClient
from itop_sync_utils import DB_CONFIG

itop = ITopClient()
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("SELECT hostname, site, rack_name FROM unified_assets WHERE device_type='server'")
for hostname, site, rack_name in cur.fetchall():
    if not site: continue
    # alt_host logic for iTop find_device
    alt_host = hostname.replace('SERVER-', 'SRV-')
    class_name, objs = itop.find_device(hostname, "", "")
    if not objs:
        class_name, objs = itop.find_device(alt_host, "", "")
        
    if objs:
        obj_id = list(objs.keys())[0]
        obj_fields = objs[obj_id]["fields"]
        current_loc_id = obj_fields.get("location_id")
        
        loc_id = itop.get_or_create_location(site, "1")
        if loc_id != current_loc_id:
            print(f"Updating {hostname} (ID={obj_id}) to Location={site} (ID={loc_id})")
            itop._post({
                "operation": "core/update",
                "class": class_name,
                "key": obj_id,
                "fields": {"location_id": loc_id}
            })
        else:
            print(f"{hostname} is already in correct location.")

