#!/usr/bin/env python3
"""
Quick CCTV Status Check
Cek berapa CCTV yang berhasil di-poll dalam periode tertentu
"""
import subprocess
import sys

def run_query(query):
    """Run PostgreSQL query"""
    cmd = [
        'psql', '-h', '192.168.101.73', '-U', 'sot_admin', '-d', 'dcim_sot',
        '-t', '-c', query
    ]
    env = {'PGPASSWORD': 'Inovasi@0918'}
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

print("=" * 60)
print("CCTV Polling Status Check")
print("=" * 60)
print()

# Check last 5 minutes
print("📊 Data dalam 5 menit terakhir:")
result = run_query("""
    SELECT 
        COUNT(*) as total_events,
        COUNT(DISTINCT serial_number) as unique_cameras
    FROM dcim_events 
    WHERE device_type = 'cctv' 
      AND event_time > NOW() - INTERVAL '5 minutes';
""")
print(result)
print()

# Check last hour
print("📊 Data dalam 1 jam terakhir:")
result = run_query("""
    SELECT 
        COUNT(*) as total_events,
        COUNT(DISTINCT serial_number) as unique_cameras
    FROM dcim_events 
    WHERE device_type = 'cctv' 
      AND event_time > NOW() - INTERVAL '1 hour';
""")
print(result)
print()

# Check last 24 hours
print("📊 Data dalam 24 jam terakhir:")
result = run_query("""
    SELECT 
        COUNT(*) as total_events,
        COUNT(DISTINCT serial_number) as unique_cameras
    FROM dcim_events 
    WHERE device_type = 'cctv' 
      AND event_time > NOW() - INTERVAL '1 day';
""")
print(result)
print()

# Top 10 cameras by event count
print("📋 Top 10 CCTV (berdasarkan jumlah events, 1 jam terakhir):")
result = run_query("""
    SELECT 
        hostname,
        serial_number,
        COUNT(*) as events
    FROM dcim_events 
    WHERE device_type = 'cctv' 
      AND event_time > NOW() - INTERVAL '1 hour'
    GROUP BY hostname, serial_number
    ORDER BY events DESC
    LIMIT 10;
""")
print(result if result else "No data")
print()

# Check if NO_SN exists
print("⚠️  CCTV dengan NO_SN (tidak teridentifikasi):")
result = run_query("""
    SELECT COUNT(*) as count_no_sn
    FROM dcim_events 
    WHERE device_type = 'cctv' 
      AND serial_number = 'NO_SN'
      AND event_time > NOW() - INTERVAL '1 hour';
""")
print(f"  Events dengan NO_SN: {result}")
print()

print("=" * 60)
print("✅ Check complete")
print("=" * 60)
