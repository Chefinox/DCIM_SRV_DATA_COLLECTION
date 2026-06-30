#!/usr/bin/env python3
"""
Populate Redis with minimal CMDB data from existing Elasticsearch documents
This is a workaround when PostgreSQL CMDB is not accessible
"""
import json
import redis
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

ES_URL = "https://10.70.0.56:9200"
ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
REDIS_HOST = "10.70.0.56"
REDIS_PORT = 6379

# Minimal CMDB data for known devices
KNOWN_DEVICES = {
    # Servers
    "J901GKXY": {"site": "FIT-Head-Office", "rack_name": "Rack Server 2", "manufacturer": "Lenovo", "model": "ThinkSystem SR650 V3"},
    "J901GKXZ": {"site": "FIT-Head-Office", "rack_name": "Rack Server 2", "manufacturer": "Lenovo", "model": "ThinkSystem SR650 V3"},
    "J901GKXX": {"site": "FIT-Head-Office", "rack_name": "Rack Server 2", "manufacturer": "Lenovo", "model": "ThinkSystem SR650 V3"},
    "HF809EP9TTE": {"site": "FIT-Head-Office", "rack_name": "Rack Server 1", "manufacturer": "Dell", "model": "PowerEdge R740"},
    
    # Network Switches
    "FIT-CORE-SW": {"site": "FIT-Head-Office", "rack_name": "Rack Network", "manufacturer": "Mikrotik", "model": "CCR2004"},
    "LINK-BALANCER": {"site": "FIT-Head-Office", "rack_name": "Rack Network", "manufacturer": "Mikrotik", "model": "CRS326"},
    
    # NAS
    "10.50.0.4": {"site": "FIT-Head-Office", "rack_name": "Rack Storage", "manufacturer": "Synology", "model": "DS920+"},
    "10.50.0.106": {"site": "FIT-Head-Office", "rack_name": "Rack Storage", "manufacturer": "Synology", "model": "DS1621+"},
}

print("=" * 70)
print("POPULATE REDIS WITH MINIMAL CMDB DATA")
print("=" * 70)

# Connect to Redis
print("\n📋 Connecting to Redis...")
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
try:
    redis_client.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    exit(1)

# Get unique devices from Elasticsearch
print("\n📊 Fetching device list from Elasticsearch...")
query = {
    "size": 0,
    "query": {"range": {"@timestamp": {"gte": "now-24h"}}},
    "aggs": {
        "devices": {
            "composite": {
                "size": 100,
                "sources": [
                    {"hostname": {"terms": {"field": "hostname.keyword"}}},
                    {"serial": {"terms": {"field": "serial_number.keyword"}}},
                    {"device_type": {"terms": {"field": "device_type.keyword"}}}
                ]
            }
        }
    }
}

resp = requests.post(
    f"{ES_URL}/dcim-metrics-unified-*/_search",
    headers={"Content-Type": "application/json"},
    json=query,
    auth=ES_AUTH,
    verify=False
)

if resp.status_code != 200:
    print(f"❌ Elasticsearch query failed: {resp.status_code}")
    exit(1)

devices = resp.json()["aggregations"]["devices"]["buckets"]
print(f"✅ Found {len(devices)} unique devices")

# Populate Redis
print("\n📝 Populating Redis cache...")
count = 0
partial_count = 0

for device in devices:
    hostname = device["key"]["hostname"]
    serial = device["key"]["serial"]
    device_type = device["key"]["device_type"]
    
    # Skip invalid serials
    if serial.upper() in ("NO_IDENTIFIER", "NO_SN", "UNKNOWN", ""):
        continue
    
    # Check if we have CMDB data for this device
    serial_upper = serial.upper()
    hostname_upper = hostname.upper()
    
    cmdb_data = None
    
    # Try exact serial match
    if serial_upper in KNOWN_DEVICES:
        cmdb_data = KNOWN_DEVICES[serial_upper].copy()
        cmdb_data["serial_number"] = serial
    # Try hostname match
    elif hostname_upper in KNOWN_DEVICES:
        cmdb_data = KNOWN_DEVICES[hostname_upper].copy()
        cmdb_data["serial_number"] = serial
    else:
        # Create partial entry with defaults
        cmdb_data = {
            "site": "FIT-Head-Office",  # Default site
            "rack_name": "Unknown",
            "manufacturer": "Unknown",
            "model": "Unknown",
            "serial_number": serial
        }
        partial_count += 1
    
    # Store in Redis with multiple keys for lookup
    serial_clean = serial.lower().strip()
    hostname_clean = hostname.lower().strip()
    
    # Primary key: serial number
    redis_client.setex(f"asset:sn:{serial_clean}", 3600, json.dumps(cmdb_data))
    
    # Secondary key: hostname
    redis_client.setex(f"asset:sn:{hostname_clean}", 3600, json.dumps(cmdb_data))
    
    count += 1

print(f"✅ Populated {count} devices in Redis")
print(f"   • {count - partial_count} with full CMDB data")
print(f"   • {partial_count} with partial data (defaults)")

# Add known devices that might not be in recent ES data
print("\n📝 Adding known devices from static list...")
static_count = 0
for serial, data in KNOWN_DEVICES.items():
    data_copy = data.copy()
    data_copy["serial_number"] = serial
    
    serial_clean = serial.lower().strip()
    redis_client.setex(f"asset:sn:{serial_clean}", 3600, json.dumps(data_copy))
    static_count += 1

print(f"✅ Added {static_count} known devices")

# Verify
print("\n🔍 Verification:")
test_serials = ["J901GKXY", "FIT-CORE-SW", "10.50.0.4"]
for serial in test_serials:
    data = redis_client.get(f"asset:sn:{serial.lower()}")
    if data:
        parsed = json.loads(data)
        print(f"   ✅ {serial}: {parsed.get('site')} / {parsed.get('rack_name')}")
    else:
        print(f"   ❌ {serial}: Not found")

print("\n" + "=" * 70)
print("✅ COMPLETE")
print("=" * 70)
print("\n⚠️  Note: This is temporary data with 1-hour TTL")
print("⚠️  For permanent fix, restore PostgreSQL CMDB connection")
print("\n💡 To extend TTL, run this script periodically or fix database connection")
