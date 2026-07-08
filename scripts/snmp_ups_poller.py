#!/usr/bin/env python3
import sys
import json
import time
import subprocess

# UPS IP and SNMPv3 Settings based on Telegraf config
UPS_IP = "192.168.100.140"
SNMP_USER = "hndept"
AUTH_PASS = "F!tech0918"
PRIV_PASS = "F!tech0918"

# OIDs from Telegraf ups-apc.conf.disabled
OIDS = {
    "system_name": ".1.3.6.1.2.1.1.5.0",
    "system_location": ".1.3.6.1.2.1.1.6.0",
    "system_description": ".1.3.6.1.2.1.1.1.0",
    "model": ".1.3.6.1.4.1.935.1.1.1.1.1.1.0",
    "status": ".1.3.6.1.4.1.935.1.1.1.4.1.1.0",
    "battery_capacity": ".1.3.6.1.4.1.935.1.1.1.2.2.1.0",
    "battery_runtime_remain": ".1.3.6.1.4.1.935.1.1.1.2.2.3.0",
    "battery_temp": ".1.3.6.1.4.1.935.1.1.1.2.2.2.0",
    "input_voltage": ".1.3.6.1.4.1.935.1.1.1.3.2.1.0",
    "output_voltage": ".1.3.6.1.4.1.935.1.1.1.4.2.1.0",
    "output_load": ".1.3.6.1.4.1.935.1.1.1.4.2.3.0",
    "serial_number": ".1.3.6.1.2.1.33.1.1.1.0",
    "firmware": ".1.3.6.1.2.1.33.1.1.3.0",
    "agent_firmware": ".1.3.6.1.2.1.33.1.1.4.0",
    "battery_status": ".1.3.6.1.2.1.33.1.2.1.0",
    "battery_seconds_on_battery": ".1.3.6.1.2.1.33.1.2.2.0",
    "battery_voltage": ".1.3.6.1.2.1.33.1.2.5.0",
    "battery_current": ".1.3.6.1.2.1.33.1.2.6.0",
    "input_frequency_L1": ".1.3.6.1.2.1.33.1.3.3.1.2.1",
    "input_frequency_L2": ".1.3.6.1.2.1.33.1.3.3.1.2.2",
    "input_frequency_L3": ".1.3.6.1.2.1.33.1.3.3.1.2.3",
    "input_voltage_L1": ".1.3.6.1.2.1.33.1.3.3.1.3.1",
    "input_voltage_L2": ".1.3.6.1.2.1.33.1.3.3.1.3.2",
    "input_voltage_L3": ".1.3.6.1.2.1.33.1.3.3.1.3.3",
    "output_frequency": ".1.3.6.1.2.1.33.1.4.2.0",
    "output_voltage_L1": ".1.3.6.1.2.1.33.1.4.4.1.2.1",
    "output_voltage_L2": ".1.3.6.1.2.1.33.1.4.4.1.2.2",
    "output_voltage_L3": ".1.3.6.1.2.1.33.1.4.4.1.2.3",
    "output_current_L1": ".1.3.6.1.2.1.33.1.4.4.1.3.1",
    "output_current_L2": ".1.3.6.1.2.1.33.1.4.4.1.3.2",
    "output_current_L3": ".1.3.6.1.2.1.33.1.4.4.1.3.3",
    "output_load_L1": ".1.3.6.1.2.1.33.1.4.4.1.5.1",
    "output_load_L2": ".1.3.6.1.2.1.33.1.4.4.1.5.2",
    "output_load_L3": ".1.3.6.1.2.1.33.1.4.4.1.5.3"
}

TAG_FIELDS = ["model", "serial_number", "firmware"]

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

def get_snmp_value(ip, oid):
    cmd = [
        "snmpwalk", "-Oqn", "-v3", "-l", "authPriv", 
        "-u", SNMP_USER, "-a", "SHA", "-A", AUTH_PASS, 
        "-x", "AES", "-X", PRIV_PASS, "-t", "2", "-r", "1",
        ip, oid
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            parts = result.stdout.split(" ", 1)
            if len(parts) == 2:
                return parse_value(parts[1])
    except Exception as e:
        sys.stderr.write(f"Error polling {oid}: {e}\\n")
    return None

def main():
    timestamp = int(time.time())
    
    tags = {
        "device_type": "ups",
        "location": "Server Room",
        "agent_host": UPS_IP
    }
    
    fields = {}
    
    for name, oid in OIDS.items():
        val = get_snmp_value(UPS_IP, oid)
        if val is not None:
            if name in TAG_FIELDS:
                tags[name] = str(val)
            else:
                fields[name] = val
                
    if fields:
        metric = {
            "name": "ups_apc",
            "tags": tags,
            "fields": fields,
            "timestamp": timestamp
        }
        print(json.dumps(metric))

if __name__ == "__main__":
    main()
