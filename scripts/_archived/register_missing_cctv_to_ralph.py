#!/usr/bin/env python3
"""
Re-register Missing CCTVs to Ralph CMDB
Recovery script untuk CCTV yang hilang setelah migrasi gagal

Context: 21 CCTV hilang dari Ralph database setelah incident migrasi dan recovery.
Script ini akan re-register mereka via Ralph API.
"""
import requests
import sys
import time
from requests.auth import HTTPDigestAuth

# Ralph API Configuration
RALPH_URL = "http://192.168.101.73:8000"
RALPH_API_KEY = "Token 1cd05b8d36e258399a52c59f1a4016addb2346a3"
RALPH_USER = "admin"
RALPH_PASS = "admin"

# CCTV Credentials (untuk query device info)
CAM_USER = "admin"
CAM_PASS = "F!tech0918"

# Missing CCTVs from Ralph (data loss dari migrasi gagal)
MISSING_CCTV_DATA = [
    {"sn": "DS-2CD1043G0E-I20200427AAWRE30076984", "model": "DS-2CD1043G0E-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568965", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568450", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568469", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1043G0E-I20200427AAWRE30076719", "model": "DS-2CD1043G0E-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568933", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1143G0E-I20210227AAWRF58406256", "model": "DS-2CD1143G0E-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568170", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1143G0E-I20210227AAWRF58406296", "model": "DS-2CD1143G0E-I", "ip": None},
    {"sn": "DS-2CD1021-I20201119AAWRE99707505", "model": "DS-2CD1021-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568951", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568954", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568952", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568968", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568966", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568967", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568953", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568949", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568950", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD1121-I20200308AAWRE17568948", "model": "DS-2CD1121-I", "ip": None},
    {"sn": "DS-2CD3121G0-I20200427AAWRE30076984", "model": "DS-2CD3121G0-I", "ip": None},
]

# All CCTV IPs to scan
CCTV_IPS = [f"192.168.1.{i}" for i in range(2, 34) if i != 32]


def get_device_info_from_camera(ip):
    """Query CCTV untuk mendapatkan serial number dan info lainnya"""
    url = f"http://{ip}/ISAPI/System/deviceInfo"
    try:
        response = requests.get(
            url,
            auth=HTTPDigestAuth(CAM_USER, CAM_PASS),
            timeout=5
        )
        if response.status_code == 200:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(response.content)
            
            sn = root.find('.//serialNumber')
            model = root.find('.//model')
            name = root.find('.//deviceName')
            
            return {
                'serial_number': sn.text if sn is not None else None,
                'model': model.text if model is not None else None,
                'device_name': name.text if name is not None else None,
            }
    except Exception as e:
        return None
    
    return None


def map_sn_to_ip():
    """Scan semua CCTV IP untuk mapping SN ke IP"""
    print("=" * 80)
    print("Step 1: Mapping Serial Numbers to IP Addresses")
    print("=" * 80)
    print()
    print("🔍 Scanning 31 CCTV IPs untuk mapping SN...")
    print()
    
    sn_to_ip_map = {}
    
    for i, ip in enumerate(CCTV_IPS, 1):
        print(f"  [{i:2d}/31] Checking {ip}...", end=" ", flush=True)
        info = get_device_info_from_camera(ip)
        
        if info and info['serial_number']:
            sn = info['serial_number']
            sn_to_ip_map[sn] = {
                'ip': ip,
                'model': info['model'],
                'device_name': info['device_name']
            }
            print(f"✓ SN: {sn[:25]}...")
        else:
            print("❌ Failed")
        
        time.sleep(0.5)  # Rate limiting
    
    print()
    print(f"✅ Found {len(sn_to_ip_map)} CCTVs with valid serial numbers")
    print()
    
    return sn_to_ip_map


def check_ralph_api():
    """Test Ralph API connection"""
    print("=" * 80)
    print("Step 2: Testing Ralph API Connection")
    print("=" * 80)
    print()
    
    # Try to get API info
    try:
        response = requests.get(
            f"{RALPH_URL}/api/",
            headers={"Authorization": RALPH_API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Ralph API connection successful")
            return True
        else:
            print(f"❌ Ralph API returned status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to connect to Ralph API: {e}")
        print()
        print("⚠️  NOTE: Script ini memerlukan Ralph API token.")
        print("   Untuk mendapatkan token:")
        print("   1. Login ke Ralph web interface")
        print("   2. Go to: Admin → Auth Token")
        print("   3. Generate token untuk user Anda")
        print("   4. Update RALPH_API_KEY di script ini")
        return False


def register_cctv_to_ralph(cctv_data, ip_info):
    """Register single CCTV to Ralph via API"""
    
    # Prepare payload for Ralph API
    payload = {
        "hostname": ip_info.get('device_name', f"CCTV-{cctv_data['sn'][:10]}"),
        "sn": cctv_data['sn'],
        "model": {
            "name": cctv_data['model'],
            "manufacturer": {"name": "Hikvision"}
        },
        "service_env": {"name": "Back Office"},
        "status": "in_use",
        "remarks": f"Re-registered after migration recovery - IP: {ip_info['ip']}",
        # Add more fields as needed based on Ralph schema
    }
    
    try:
        response = requests.post(
            f"{RALPH_URL}/api/data-center-assets/",
            headers={
                "Authorization": RALPH_API_KEY,
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            return True, "Success"
        else:
            return False, f"Status {response.status_code}: {response.text[:100]}"
            
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 80)
    print("Re-register Missing CCTVs to Ralph CMDB")
    print("Recovery Script - Data Loss dari Migrasi Gagal")
    print("=" * 80)
    print()
    print(f"📊 Total CCTV to re-register: {len(MISSING_CCTV_DATA)}")
    print()
    
    # Step 1: Map SN to IP
    sn_to_ip_map = map_sn_to_ip()
    
    # Update MISSING_CCTV_DATA with IP info
    for cctv in MISSING_CCTV_DATA:
        if cctv['sn'] in sn_to_ip_map:
            cctv['ip'] = sn_to_ip_map[cctv['sn']]['ip']
            cctv['device_name'] = sn_to_ip_map[cctv['sn']]['device_name']
    
    # Count how many we can register
    with_ip = [c for c in MISSING_CCTV_DATA if c['ip']]
    without_ip = [c for c in MISSING_CCTV_DATA if not c['ip']]
    
    print(f"📊 Mapping Results:")
    print(f"   - CCTVs with IP found: {len(with_ip)}")
    print(f"   - CCTVs without IP: {len(without_ip)}")
    print()
    
    if without_ip:
        print("⚠️  CCTVs without IP (offline atau tidak bisa di-query):")
        for cctv in without_ip:
            print(f"   - {cctv['sn'][:30]}... ({cctv['model']})")
        print()
    
    # Step 2: Check Ralph API
    if not check_ralph_api():
        print()
        print("=" * 80)
        print("❌ Cannot proceed without Ralph API access")
        print("=" * 80)
        print()
        print("📋 Manual Registration Required:")
        print()
        print("Login ke Ralph dan register manual dengan data berikut:")
        print()
        for i, cctv in enumerate(with_ip, 1):
            print(f"{i:2d}. SN: {cctv['sn']}")
            print(f"    Model: {cctv['model']}")
            print(f"    IP: {cctv['ip']}")
            print(f"    Name: {cctv.get('device_name', 'N/A')}")
            print()
        
        return
    
    # Step 3: Register CCTVs
    print()
    print("=" * 80)
    print("Step 3: Registering CCTVs to Ralph")
    print("=" * 80)
    print()
    
    success_count = 0
    failed_count = 0
    
    for i, cctv in enumerate(with_ip, 1):
        print(f"[{i:2d}/{len(with_ip)}] Registering {cctv['sn'][:30]}...", end=" ", flush=True)
        
        ip_info = sn_to_ip_map.get(cctv['sn'], {})
        success, message = register_cctv_to_ralph(cctv, ip_info)
        
        if success:
            print(f"✅ {message}")
            success_count += 1
        else:
            print(f"❌ {message}")
            failed_count += 1
        
        time.sleep(1)  # Rate limiting
    
    # Summary
    print()
    print("=" * 80)
    print("Registration Summary")
    print("=" * 80)
    print(f"  ✅ Successfully registered: {success_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  ⏭️  Skipped (no IP): {len(without_ip)}")
    print()
    
    if success_count > 0:
        print("✅ Re-registration complete!")
        print()
        print("Next steps:")
        print("  1. Verify di Ralph web interface")
        print("  2. Run ralph_cmdb_sync.py untuk sync metadata")
        print("  3. Check logs untuk memastikan tidak ada warning lagi")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
