#!/usr/bin/env python3
"""
Quick test Ralph API connection dengan token
"""
import requests
import json

RALPH_URL = "http://192.168.101.73:8000"
RALPH_API_KEY = "Token 1cd05b8d36e258399a52c59f1a4016addb2346a3"

print("=" * 70)
print("Testing Ralph API Connection")
print("=" * 70)
print()

# Test 1: API Root
print("Test 1: API Root Endpoint")
try:
    response = requests.get(
        f"{RALPH_URL}/api/",
        headers={"Authorization": RALPH_API_KEY},
        timeout=10
    )
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        print("  ✅ API connection successful")
        data = response.json()
        print(f"  Available endpoints: {len(data)} endpoints")
    else:
        print(f"  ❌ Failed: {response.text[:200]}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print()

# Test 2: Get Data Center Assets
print("Test 2: Data Center Assets Endpoint")
try:
    response = requests.get(
        f"{RALPH_URL}/api/data-center-assets/",
        headers={"Authorization": RALPH_API_KEY},
        timeout=10
    )
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ Can access assets")
        print(f"  Total assets: {data.get('count', 'N/A')}")
    else:
        print(f"  ❌ Failed: {response.text[:200]}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print()

# Test 3: Search for existing CCTV
print("Test 3: Search for Existing CCTV")
try:
    response = requests.get(
        f"{RALPH_URL}/api/data-center-assets/?search=CCTV",
        headers={"Authorization": RALPH_API_KEY},
        timeout=10
    )
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        count = data.get('count', 0)
        print(f"  ✅ Found {count} CCTV assets in Ralph")
        
        if count > 0 and 'results' in data:
            print(f"  Sample CCTVs:")
            for asset in data['results'][:3]:
                print(f"    - {asset.get('hostname', 'N/A')} (SN: {asset.get('sn', 'N/A')})")
    else:
        print(f"  ❌ Failed: {response.text[:200]}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print()
print("=" * 70)
print("✅ API Test Complete")
print("=" * 70)
