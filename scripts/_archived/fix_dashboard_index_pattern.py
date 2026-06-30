#!/usr/bin/env python3
"""
Fix dcim-metrics-* index pattern with proper field mappings
"""
import json
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

KIBANA_URL = "http://10.70.0.56:5601"
ES_URL = "https://10.70.0.56:9200"
INDEX_PATTERN_ID = "dcim-metrics-*"
INDEX_PATTERN = "dcim-metrics-unified-*"
AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}

print("=" * 70)
print("FIX DCIM-METRICS-* INDEX PATTERN")
print("=" * 70)

# Get field mappings from Elasticsearch
print("\n📋 Fetching field mappings from Elasticsearch...")
resp = requests.get(f"{ES_URL}/{INDEX_PATTERN}/_mapping", auth=AUTH, verify=False)
if resp.status_code != 200:
    print(f"❌ Failed to get mappings: {resp.status_code}")
    exit(1)

mappings = resp.json()
all_fields = {}

# Extract all fields
for index_name, index_data in mappings.items():
    properties = index_data.get("mappings", {}).get("properties", {})
    
    def extract_fields(props, prefix=""):
        for field_name, field_info in props.items():
            full_name = f"{prefix}{field_name}" if prefix else field_name
            field_type = field_info.get("type", "object")
            
            if field_type == "object" or field_type == "nested":
                nested_props = field_info.get("properties", {})
                if nested_props:
                    extract_fields(nested_props, f"{full_name}.")
                else:
                    all_fields[full_name] = {"type": field_type}
            else:
                all_fields[full_name] = {"type": field_type}
                
                # Add .keyword for text fields
                if field_type == "text" and "fields" in field_info:
                    if "keyword" in field_info["fields"]:
                        all_fields[f"{full_name}.keyword"] = {"type": "keyword"}
    
    extract_fields(properties)

print(f"✅ Found {len(all_fields)} fields")

# Build field list and format map for Kibana
fields = []
field_format_map = {}

for field_name, field_info in sorted(all_fields.items()):
    field_type = field_info["type"]
    
    # Map ES types to Kibana types
    kibana_type = field_type
    if field_type in ["long", "integer", "short", "byte", "double", "float", "half_float", "scaled_float"]:
        kibana_type = "number"
        # Force rounding to 2 decimals for floating point fields
        if field_type in ["double", "float", "half_float", "scaled_float"] or "Pct" in field_name or "GB" in field_name or "TB" in field_name or "MB" in field_name or "Usage" in field_name:
            field_format_map[field_name] = {
                "id": "number",
                "params": {"pattern": "0,0.[00]"}
            }
        
        # Format Bytes fields correctly
        if "Bytes" in field_name:
            field_format_map[field_name] = {
                "id": "bytes",
                "params": {"pattern": "0,0.[00]b"}
            }
    elif field_type == "date":
        kibana_type = "date"
    elif field_type == "boolean":
        kibana_type = "boolean"
    elif field_type == "ip":
        kibana_type = "ip"
    elif field_type in ["text", "keyword"]:
        kibana_type = "string"
    else:
        kibana_type = "string"
    
    field_obj = {
        "name": field_name,
        "type": kibana_type,
        "esTypes": [field_type],
        "searchable": True,
        "aggregatable": field_type != "text",
        "readFromDocValues": field_type not in ["text", "geo_shape"],
    }
    fields.append(field_obj)

print(f"✅ Prepared {len(fields)} field definitions")
print(f"✅ Created {len(field_format_map)} custom number formats")

# Delete old index pattern
print("\n🗑️  Deleting old index pattern...")
requests.delete(
    f"{KIBANA_URL}/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}",
    headers=HEADERS, auth=AUTH
)

# Create new index pattern with fields
print("📝 Creating new index pattern with field mappings...")
payload = {
    "attributes": {
        "title": INDEX_PATTERN,
        "timeFieldName": "@timestamp",
        "fields": json.dumps(fields),
        "fieldFormatMap": json.dumps(field_format_map)
    }
}

resp = requests.post(
    f"{KIBANA_URL}/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}?overwrite=true",
    headers=HEADERS, json=payload, auth=AUTH
)

if resp.status_code in (200, 201):
    print("✅ Index pattern created successfully!")
    print(f"\n📊 Index Pattern ID: {INDEX_PATTERN_ID}")
    print(f"📊 Pattern: {INDEX_PATTERN}")
    print(f"📊 Fields: {len(fields)}")
else:
    print(f"❌ Failed: {resp.status_code}")
    print(resp.text)
    exit(1)

print("\n" + "=" * 70)
print("✅ COMPLETE - Dashboard should now load properly")
print("=" * 70)
print(f"\n🔗 Dashboard URL: {KIBANA_URL}/app/dashboards#/view/dcim-monitoring")
