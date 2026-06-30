#!/usr/bin/env python3
"""
Quick verification script untuk dashboard Kibana.
Cek apakah data tersedia untuk setiap device type.
"""
import requests
from datetime import datetime, timedelta

ES_URL = "https://10.70.0.56:9200"
ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def check_data(device_type):
    """Check if data exists for device type"""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"device_type": device_type}},
                    {"range": {"@timestamp": {"gte": "now-1h"}}}
                ]
            }
        },
        "size": 0
    }
    
    try:
        resp = requests.post(
            f"{ES_URL}/dcim-metrics-unified-*/_search",
            json=query,
            auth=ES_AUTH,
            verify=False,
            timeout=5
        )
        if resp.status_code == 200:
            count = resp.json()['hits']['total']['value']
            return count
        return 0
    except Exception as e:
        print(f"  ❌ Error checking {device_type}: {e}")
        return 0

def check_sample_fields(device_type, sample_field):
    """Check if specific field has data"""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"device_type": device_type}},
                    {"exists": {"field": sample_field}},
                    {"range": {"@timestamp": {"gte": "now-1h"}}}
                ]
            }
        },
        "size": 1,
        "_source": [sample_field, "hostname"]
    }
    
    try:
        resp = requests.post(
            f"{ES_URL}/dcim-metrics-unified-*/_search",
            json=query,
            auth=ES_AUTH,
            verify=False,
            timeout=5
        )
        if resp.status_code == 200:
            hits = resp.json()['hits']['hits']
            if hits:
                return True, hits[0]['_source']
        return False, None
    except:
        return False, None

print("=" * 70)
print("DCIM DASHBOARD DATA VERIFICATION")
print("=" * 70)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Checking data from last 1 hour...\n")

# Device types to check
device_checks = [
    ("network_switch", "raw_fields.ifOperStatus", "Interface Status"),
    ("ups", "raw_fields.upsBatteryCapacity", "Battery Capacity"),
    ("nas", "raw_fields.disk_temp", "Disk Temperature"),
    ("server", "raw_fields.reading_rpm", "Fan Speed"),
    ("cctv", "raw_fields.deviceUpTime", "Device Uptime"),
    ("nvr", "raw_fields.capacity", "HDD Capacity"),
]

total_docs = 0
working_types = 0

for device_type, sample_field, field_name in device_checks:
    count = check_data(device_type)
    total_docs += count
    
    if count > 0:
        has_field, sample = check_sample_fields(device_type, sample_field)
        status = "✅" if has_field else "⚠️"
        working_types += 1 if has_field else 0
        
        print(f"{status} {device_type:15} : {count:6,} docs", end="")
        if has_field and sample:
            hostname = sample.get('hostname', 'N/A')
            print(f"  | Sample: {hostname}")
        elif count > 0:
            print(f"  | No {field_name} data")
        else:
            print()
    else:
        print(f"❌ {device_type:15} : No data in last hour")

print("\n" + "=" * 70)
print(f"Summary:")
print(f"  Total documents: {total_docs:,}")
print(f"  Device types with data: {working_types}/{len(device_checks)}")
print(f"  Dashboard URL: http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard")
print("=" * 70)

if working_types < len(device_checks):
    print("\n⚠️  Some device types have no data or missing fields.")
    print("   This is normal if those devices are not currently monitored.")
    print("   Panels for those types will show 'No results found'.")
else:
    print("\n✅ All device types have data! Dashboard should be fully populated.")
