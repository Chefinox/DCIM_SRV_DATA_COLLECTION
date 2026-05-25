#!/usr/bin/env python3
"""
CCTV Status Checker via NVR
Query NVR untuk melihat status online/offline semua CCTV yang terhubung
"""
import subprocess
import re
from datetime import datetime

NVR_IP = "192.168.1.254"
NVR_USER = "admin"
NVR_PASS = "qRvbi883=Zk[Q)@5"

def get_nvr_channels():
    """Get all channels from NVR using curl"""
    cmd = [
        'curl', '-s', '--digest', '-u', f'{NVR_USER}:{NVR_PASS}',
        f'http://{NVR_IP}/ISAPI/ContentMgmt/InputProxy/channels'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        xml_data = result.stdout
        
        if not xml_data or len(xml_data) < 100:
            print(f"Error: Empty or invalid response from NVR")
            return []
        
        # Parse XML manually - find all <id>, <name>, <ipAddress> in sequence
        channels = []
        lines = xml_data.split('\n')
        
        current_channel = {}
        for line in lines:
            line = line.strip()
            
            if '<id>' in line and '</id>' in line:
                ch_id = re.search(r'<id>(\d+)</id>', line)
                if ch_id:
                    current_channel['id'] = ch_id.group(1)
            
            elif '<name>' in line and '</name>' in line:
                name = re.search(r'<name>(.*?)</name>', line)
                if name:
                    current_channel['name'] = name.group(1).replace('&amp;', '&')
            
            elif '<ipAddress>' in line and '</ipAddress>' in line:
                ip = re.search(r'<ipAddress>(.*?)</ipAddress>', line)
                if ip:
                    current_channel['ip'] = ip.group(1)
                    
                    # Complete channel found
                    if 'id' in current_channel and 'name' in current_channel:
                        channels.append(current_channel.copy())
                        current_channel = {}
        
        return channels
    except Exception as e:
        print(f"Error getting channels: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_channel_status():
    """Get online/offline status of all channels using curl"""
    cmd = [
        'curl', '-s', '--digest', '-u', f'{NVR_USER}:{NVR_PASS}',
        f'http://{NVR_IP}/ISAPI/ContentMgmt/InputProxy/channels/status'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        xml_data = result.stdout
        
        # Parse status
        status_map = {}
        status_blocks = re.findall(r'<InputProxyChannelStatus.*?>(.*?)</InputProxyChannelStatus>', xml_data, re.DOTALL)
        
        for block in status_blocks:
            ch_id = re.search(r'<id>(\d+)</id>', block)
            online = re.search(r'<online>(.*?)</online>', block)
            
            if ch_id and online:
                status_map[ch_id.group(1)] = online.group(1).lower() == 'true'
        
        return status_map
    except Exception as e:
        print(f"Error getting status: {e}")
        return {}

def main():
    print("=" * 80)
    print(f"CCTV Status Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"NVR: {NVR_IP}")
    print("=" * 80)
    
    # Get channels and status
    channels = get_nvr_channels()
    status_map = get_channel_status()
    
    if not channels:
        print("❌ Failed to retrieve channel information")
        return
    
    # Combine data
    online_count = 0
    offline_count = 0
    
    print(f"\n{'ID':<4} {'IP':<16} {'Status':<8} {'Location'}")
    print("-" * 80)
    
    for ch in sorted(channels, key=lambda x: int(x['id'])):
        ch_id = ch['id']
        is_online = status_map.get(ch_id, False)
        status_icon = "🟢" if is_online else "🔴"
        status_text = "ONLINE" if is_online else "OFFLINE"
        
        if is_online:
            online_count += 1
        else:
            offline_count += 1
        
        print(f"{ch_id:<4} {ch['ip']:<16} {status_icon} {status_text:<6} {ch['name']}")
    
    print("-" * 80)
    print(f"\n📊 Summary:")
    print(f"   Total Channels: {len(channels)}")
    print(f"   🟢 Online:  {online_count}")
    print(f"   🔴 Offline: {offline_count}")
    print(f"   📈 Uptime:  {online_count/len(channels)*100:.1f}%")
    
    if offline_count > 0:
        print(f"\n⚠️  Warning: {offline_count} camera(s) offline!")
    else:
        print(f"\n✅ All cameras online!")

if __name__ == "__main__":
    main()
