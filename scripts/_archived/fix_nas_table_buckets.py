import requests
import json
import base64

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    "kbn-xsrf": "true",
    "Authorization": "Basic " + base64.b64encode(b"elastic:C+H+pFb*aIAqWcOo-X8q").decode('utf-8'),
    "Content-Type": "application/json"
}

def fix_table():
    viz_id = "dcim-mon-nas-list"
    resp = requests.get(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}", headers=HEADERS)
    if resp.status_code != 200:
        print("Failed to fetch table:", resp.text)
        return
        
    viz = resp.json()
    attrs = viz["attributes"]
    vis_state = json.loads(attrs["visState"])
    
    aggs = vis_state["aggs"]
    
    for agg in aggs:
        if agg.get("schema") == "bucket" and agg.get("type") == "terms":
            field = agg["params"].get("field")
            if field == "hostname.keyword":
                agg["params"]["field"] = "tag.hostname.keyword"
            elif field == "ip.keyword":
                agg["params"]["field"] = "tag.ip.keyword"
            elif field == "serial_number.keyword":
                agg["params"]["field"] = "tag.serial_number.keyword"
                
    vis_state["aggs"] = aggs
    attrs["visState"] = json.dumps(vis_state)
    
    put_resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
        headers=HEADERS, json={"attributes": attrs, "references": viz["references"]}
    )
    if put_resp.status_code in (200, 201):
        print("✅ Fixed NAS Devices Table buckets")
    else:
        print("❌ Failed to update table:", put_resp.text)

if __name__ == "__main__":
    fix_table()
