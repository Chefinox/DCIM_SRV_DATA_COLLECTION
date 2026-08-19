#!/usr/bin/env python3
import sys
sys.path.append("/opt/nifi/nifi-current")
import json
import time
import subprocess

import sys
import json
import traceback
from datetime import datetime, timezone

def global_exception_handler(exc_type, exc_value, exc_traceback):
    error_event = {
        "event_id": "error-" + str(int(datetime.now(timezone.utc).timestamp())),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_system": "python_poller",
        "resource_type": "script",
        "event_type": "error",
        "error_message": str(exc_value),
        "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    }
    print(json.dumps(error_event))

sys.excepthook = global_exception_handler



from src.utils.rate_limiter import get_limiter
from src.utils.kill_switch import PollerKillSwitch

IPS = [
    "10.50.0.105", "10.50.0.106", "10.50.0.107",
    "10.50.0.108", "10.50.0.109", "10.50.0.110"
]

def parse_value(val_str):
    if val_str is None: return None
    val_str = val_str.strip()
    if val_str.startswith('"') and val_str.endswith('"'):
        val_str = val_str[1:-1]
    
    try:
        return int(val_str)
    except ValueError:
        pass
        
    try:
        return float(val_str)
    except ValueError:
        pass
        
    return val_str

def snmp_walk(ip, oid):
    cmd = [
        "snmpwalk", "-v3", "-l", "authPriv", "-u", "nas_user",
        "-a", "SHA", "-A", "auth_pass123", "-x", "AES", "-X", "priv_pass123",
        ip, oid
    ]
    snmp_data = {}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "=" in line:
                parts = line.split("=", 1)
                full_oid = parts[0].strip()
                val_parts = parts[1].split(":", 1)
                if len(val_parts) > 1:
                    val = val_parts[1].strip()
                    snmp_data[full_oid] = val
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
    return snmp_data

def poll_nas():
    limiter = get_limiter('nas_rest')
    kill_switch = PollerKillSwitch('nas')
    
    if kill_switch.is_killed():
        sys.stderr.write("INFO: Poller killed by kill switch.\n")
        return

    for ip in IPS:
        if not limiter.acquire():
            sys.stderr.write(f"WARN: Rate limit timeout for {ip}\n")
            continue
            
        try:
            # 1. Global scalars
            global_oids = [
                (".1.3.6.1.2.1.1.5.0", "hostname"),
                (".1.3.6.1.4.1.6574.1.5.1.0", "model"),
                (".1.3.6.1.4.1.6574.1.5.2.0", "serial_number"),
                (".1.3.6.1.4.1.6574.1.5.3.0", "firmware"),
                (".1.3.6.1.4.1.6574.1.2.0", "system_temp")
            ]
            
            base_tags = {"device_type": "nas", "ip": ip}
            fields = {}
            
            for oid, name in global_oids:
                data = snmp_walk(ip, oid)
                if oid in data:
                    if name == "system_temp":
                        fields[name] = parse_value(data[oid])
                    else:
                        base_tags[name] = parse_value(data[oid])
                        
            # 2. Disk Table
            disk_table_oid = ".1.3.6.1.4.1.6574.2.1"
            disk_data = snmp_walk(ip, disk_table_oid)
            
            # Group by index
            disks = {}
            for full_oid, val in disk_data.items():
                parts = full_oid.split('.')
                idx = parts[-1]
                col = parts[-2]
                
                if idx not in disks:
                    disks[idx] = {}
                    
                if col == "2": disks[idx]["disk_id"] = parse_value(val)
                elif col == "3": disks[idx]["model"] = parse_value(val)
                elif col == "4": disks[idx]["status"] = parse_value(val)
                elif col == "5": disks[idx]["temperature"] = parse_value(val)
                
            fields["disks"] = list(disks.values())
            
            # Print JSON Line
            record = {
                "name": "nas_metrics",
                "timestamp": int(time.time() * 1e9),
                "tags": base_tags,
                "fields": fields
            }
            print(json.dumps(record))
        except Exception as e:
            sys.stderr.write(f"ERROR processing {ip}: {e}\n")

if __name__ == "__main__":
    poll_nas()
