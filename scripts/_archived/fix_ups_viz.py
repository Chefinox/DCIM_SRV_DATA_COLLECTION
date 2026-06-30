import json
import base64
import requests

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    "kbn-xsrf": "true",
    "Authorization": "Basic " + base64.b64encode(b"elastic:C+H+pFb*aIAqWcOo-X8q").decode('utf-8')
}

VIZ_IDS = [
    "dcim-mon-ups-battery",
    "dcim-mon-ups-load",
    "dcim-mon-ups-battery-time",
    "dcim-mon-ups-load-time",
    "dcim-mon-ups-list"
]

def replace_fields(text):
    text = text.replace("tag.device_type", "tag.device_type.keyword")
    
    # Update groupings for the table
    text = text.replace("tag.hostname", "tag.hostname.keyword")
    text = text.replace("tag.site", "tag.site.keyword")
    text = text.replace("tag.rack_name", "tag.rack_name.keyword")
    text = text.replace("tag.model", "tag.model.keyword")
    
    return text

def fix_visualizations():
    for viz_id in VIZ_IDS:
        print(f"Fetching {viz_id}...")
        resp = requests.get(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}", headers=HEADERS)
        if resp.status_code != 200:
            print(f"Error fetching {viz_id}: {resp.text}")
            continue
            
        data = resp.json()
        
        # Modify visState
        vis_state_str = data["attributes"]["visState"]
        new_vis_state_str = replace_fields(vis_state_str)
        data["attributes"]["visState"] = new_vis_state_str
        
        # Modify searchSourceJSON (for the filter)
        search_source_str = data["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"]
        new_search_source_str = replace_fields(search_source_str)
        data["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"] = new_search_source_str
        
        # Remove fields that prevent successful update
        attributes = data["attributes"]
        
        payload = {
            "attributes": attributes
        }
        
        print(f"Updating {viz_id}...")
        put_resp = requests.put(
            f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}", 
            headers=HEADERS,
            json=payload
        )
        
        if put_resp.status_code == 200:
            print(f"Success updating {viz_id}")
        else:
            print(f"Error updating {viz_id}: {put_resp.text}")

if __name__ == "__main__":
    fix_visualizations()
