#!/usr/bin/env python3
"""
Check which CCTVs are missing from Ralph CMDB
"""
import re
import sys

# All 31 CCTV IPs (192.168.1.2-33, skip .32)
ALL_CCTV_IPS = [f"192.168.1.{i}" for i in range(2, 34) if i != 32]

print("=" * 70)
print("CCTV Missing from Ralph CMDB")
print("=" * 70)
print()

# Read ralph sync log
log_file = "/home/infra/dcim_metrics_project/logs/ralph_cmdb_sync.log"
missing_sns = set()
missing_ips = set()

try:
    with open(log_file, 'r') as f:
        for line in f:
            if "CCTV" in line and "tidak ditemukan di Ralph" in line:
                # Extract SN
                sn_match = re.search(r'SN ([A-Z0-9-]+)', line)
                if sn_match:
                    missing_sns.add(sn_match.group(1))
                
                # Extract IP if present
                ip_match = re.search(r'192\.168\.1\.\d+', line)
                if ip_match:
                    missing_ips.add(ip_match.group(0))
except FileNotFoundError:
    print(f"⚠️  Log file not found: {log_file}")
    sys.exit(1)

print(f"📊 Total CCTV yang seharusnya ada: {len(ALL_CCTV_IPS)}")
print(f"⚠️  CCTV dengan SN tidak ditemukan di Ralph: {len(missing_sns)}")
print()

if missing_sns:
    print("📋 Serial Numbers yang belum terdaftar di Ralph:")
    print("-" * 70)
    for i, sn in enumerate(sorted(missing_sns), 1):
        print(f"  {i:2d}. {sn}")
    print()

if missing_ips:
    print("📋 IP Address yang terdeteksi bermasalah:")
    print("-" * 70)
    for ip in sorted(missing_ips, key=lambda x: int(x.split('.')[-1])):
        print(f"  • {ip}")
    print()

# Check which IPs might not be polled yet
print("💡 Kemungkinan IP yang belum di-poll:")
print("-" * 70)
print("  (Ini adalah semua 31 IP CCTV yang dikonfigurasi)")
for i, ip in enumerate(ALL_CCTV_IPS, 1):
    status = "⚠️  Belum di Ralph" if ip in missing_ips else "✓"
    print(f"  {i:2d}. {ip:15s} {status}")

print()
print("=" * 70)
print("✅ Check complete")
print()
print("💡 Untuk mendaftarkan CCTV ke Ralph, gunakan:")
print("   python3 scripts/register_cctv_to_ralph.py")
print("=" * 70)
