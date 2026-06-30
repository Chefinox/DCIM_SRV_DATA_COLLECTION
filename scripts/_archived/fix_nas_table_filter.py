import requests
import json
import base64

KIBANA_URL = "http://localhost:5601"
HEADERS = {
    "kbn-xsrf": "true",
    "Authorization": "Basic " + base64.b64encode(b"elastic:C+H+pFb*aIAqWcOo-X8q").decode('utf-8'),
    "Content-Type": "application/json"
}

def fix_table_filter():
    viz_id = "dcim-mon-nas-list"
    resp = requests.get(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}", headers=HEADERS)
    if resp.status_code != 200:
        print("Failed to fetch table:", resp.text)
        return
        
    viz = resp.json()
    attrs = viz["attributes"]
    
    # Fix the searchSourceJSON filter
    search_source_str = attrs["kibanaSavedObjectMeta"]["searchSourceJSON"]
    search_source = json.loads(search_source_str)
    
    filters = search_source.get("filter", [])
    for f in filters:
        if "meta" in f and f["meta"].get("key") == "device_type.keyword":
            f["meta"]["key"] = "tag.device_type.keyword"
        if "query" in f and "match_phrase" in f["query"]:
            if "device_type.keyword" in f["query"]["match_phrase"]:
                val = f["query"]["match_phrase"].pop("device_type.keyword")
                f["query"]["match_phrase"]["tag.device_type.keyword"] = val
                
    search_source["filter"] = filters
    attrs["kibanaSavedObjectMeta"]["searchSourceJSON"] = json.dumps(search_source)
    
    put_resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
        headers=HEADERS, json={"attributes": attrs, "references": viz["references"]}
    )
    if put_resp.status_code in (200, 201):
        print("✅ Fixed NAS Devices Table filter")
    else:
        print("❌ Failed to update table filter:", put_resp.text)

if __name__ == "__main__":
    fix_table_filter()
