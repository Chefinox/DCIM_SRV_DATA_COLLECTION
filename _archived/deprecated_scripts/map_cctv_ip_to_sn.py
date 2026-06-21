#!/usr/bin/env python3
"""
Map CCTV Serial Numbers to IP Addresses
Query each CCTV to get its serial number and create mapping
"""
import requests
import sys
from requests.auth import HTTPDigestAuth
from xml.etree import ElementTree as ET

# Credentials.
# Catatan 2026-05-25:
# - Beberapa kamera, termasuk 192.168.1.22, dapat diping dan halaman login web muncul.
# - Login admin dengan F!tech0918 / F!tech@0918 / 12345 gagal.
# - Jika scan tetap 401 Unauthorized, credential kamera perlu reset/update di secret HIKVISION_CAM_PASS.
CAM_USER = "admin"
CAM_PASS = "F!tech0918"

# All 31 CCTV IPs
CCTV_IPS = [f"192.168.1.{i}" for i in range(2, 34) if i != 32]

# Missing SNs from Ralph
MISSING_SNS = [
    "DS-2CD1043G0E-I20200427AAWRE30076984",
    "DS-2CD1121-I20200308AAWRE17568965",
    "DS-2CD1121-I20200308AAWRE17568450",
    "DS-2CD1121-I20200308AAWRE17568469",
    "DS-2CD1043G0E-I20200427AAWRE30076719",
    "DS-2CD1121-I20200308AAWRE17568933",
    "DS-2CD1143G0E-I20210227AAWRF58406256",
    "DS-2CD1121-I20200308AAWRE17568170",
    "DS-2CD1143G0E-I20210227AAWRF58406296",
    "DS-2CD1021-I20201119AAWRE99707505",
    "DS-2CD1121-I20200308AAWRE17568951",
    "DS-2CD1121-I20200308AAWRE17568954",
    "DS-2CD1121-I20200308AAWRE17568952",
    "DS-2CD1121-I20200308AAWRE17568968",
    "DS-2CD1121-I20200308AAWRE17568966",
    "DS-2CD1121-I20200308AAWRE17568967",
    "DS-2CD1121-I20200308AAWRE17568953",
    "DS-2CD1121-I20200308AAWRE17568949",
    "DS-2CD1121-I20200308AAWRE17568950",
    "DS-2CD1121-I20200308AAWRE17568948",
    "DS-2CD3121G0-I20200427AAWRE30076984",
]

def get_device_info(ip):
    """Get device info from CCTV"""
    url = f"http://{ip}/ISAPI/System/deviceInfo"
    try:
        response = requests.get(
            url,
            auth=HTTPDigestAuth(CAM_USER, CAM_PASS),
            timeout=5
        )
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            sn = root.find('.//serialNumber')
            model = root.find('.//model')
            name = root.find('.//deviceName')
            
            return {
                'ip': ip,
                'serial_number': sn.text if sn is not None else 'UNKNOWN',
                'model': model.text if model is not None else 'UNKNOWN',
                'name': name.text if name is not None else 'UNKNOWN',
            }
    except Exception as e:
        return {'ip': ip, 'error': str(e)}
    
    return {'ip': ip, 'error': 'Failed to connect'}

print("=" * 80)
print("CCTV IP to Serial Number Mapping")
print("=" * 80)
print()
print("🔍 Scanning 31 CCTV IPs...")
print()

results = []
missing_found = []

for i, ip in enumerate(CCTV_IPS, 1):
    print(f"  [{i:2d}/31] Checking {ip}...", end=" ", flush=True)
    info = get_device_info(ip)
    
    if 'error' in info:
        print(f"❌ {info['error']}")
    else:
        sn = info['serial_number']
        is_missing = sn in MISSING_SNS
        status = "⚠️  BELUM DI RALPH" if is_missing else "✓"
        print(f"{status} SN: {sn[:20]}...")
        
        if is_missing:
            missing_found.append(info)
    
    results.append(info)

print()
print("=" * 80)
print(f"📊 Summary")
print("=" * 80)
print(f"  Total CCTV scanned: {len(CCTV_IPS)}")
print(f"  Successfully queried: {len([r for r in results if 'error' not in r])}")
print(f"  Failed to query: {len([r for r in results if 'error' in r])}")
print(f"  Missing from Ralph: {len(missing_found)}")
print()

if missing_found:
    print("=" * 80)
    print("⚠️  CCTV yang Belum di Ralph (dengan IP Address)")
    print("=" * 80)
    print()
    print(f"{'No':<4} {'IP Address':<16} {'Serial Number':<40} {'Model':<20}")
    print("-" * 80)
    
    for i, info in enumerate(missing_found, 1):
        print(f"{i:<4} {info['ip']:<16} {info['serial_number']:<40} {info['model']:<20}")
    
    print()
    print("💡 Untuk mendaftarkan ke Ralph:")
    print("   1. Login ke Ralph web interface")
    print("   2. Add Device → IP Camera")
    print("   3. Input Serial Number dan IP Address dari tabel di atas")
    print()

print("=" * 80)
print("✅ Scan complete")
print("=" * 80)
