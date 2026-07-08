#!/usr/bin/env python3
import sys
import json
import time
import subprocess

IPS = ["172.16.35.1", "172.16.35.2", "172.16.35.3", "172.16.35.5", "172.16.35.6"]

OIDS = [
    ".1.3.6.1.2.1.1",           # System
    ".1.3.6.1.2.1.2.2",         # Interfaces status
    ".1.3.6.1.2.1.31.1.1",      # Interfaces stats (ifXTable)
    ".1.3.6.1.2.1.25.2",        # Storage/HR
    ".1.3.6.1.4.1.14988.1.1.1", # Mikrotik specific (CPU, etc)
]

def parse_value(val_str):
    if val_str is None: return None
    val_str = val_str.strip()
    # snmpwalk -Oqn sometimes quotes strings
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

def main():
    timestamp = int(time.time())
    
    for ip in IPS:
        snmp_data = {}
        for oid_prefix in OIDS:
            try:
                # snmpwalk -Oqn outputs: .1.3.6... value
                cmd = ["snmpwalk", "-Oqn", "-v2c", "-c", "public", "-t", "2", "-r", "1", ip, oid_prefix]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Even if returncode != 0 (e.g. lexicographic error), snmpwalk still outputs whatever it gathered to stdout
                for line in result.stdout.splitlines():
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        oid = parts[0]
                        if not oid.startswith("."):
                            oid = "." + oid
                        snmp_data[oid] = parse_value(parts[1])
            except Exception as e:
                sys.stderr.write(f"Error polling {ip} at {oid_prefix}: {e}\n")
                
        if not snmp_data:
            continue
            
        base_tags = {
            "device_type": "network",
            "ip": ip
        }
        
        tag_map = {
            ".1.3.6.1.2.1.1.5.0": "hostname",
            ".1.3.6.1.2.1.1.1.0": "model",
            ".1.3.6.1.4.1.14988.1.1.7.3.0": "serial_number",
            ".1.3.6.1.4.1.14988.1.1.7.4.0": "firmware"
        }
        
        for oid, tag_name in tag_map.items():
            if oid in snmp_data:
                base_tags[tag_name] = str(snmp_data[oid])
                
        field_map = {
            ".1.3.6.1.4.1.2021.11.10.0": "cpu_load",
            ".1.3.6.1.2.1.25.2.3.1.6.65536": "memory_used_kb",
            ".1.3.6.1.2.1.25.2.2.0": "memory_total_kb"
        }
        
        base_fields = {}
        for oid, field_name in field_map.items():
            if oid in snmp_data:
                base_fields[field_name] = snmp_data[oid]
                
        if base_fields:
            mikrotik_metric = {
                "name": "mikrotik",
                "tags": base_tags,
                "fields": base_fields,
                "timestamp": timestamp
            }
            print(json.dumps(mikrotik_metric))
            
        interfaces = {}
        for oid, val in snmp_data.items():
            if oid.startswith(".1.3.6.1.2.1.31.1.1.1.1."):
                idx = oid.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["if_name"] = str(val)
            elif oid.startswith(".1.3.6.1.2.1.2.2.1.8."):
                idx = oid.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["if_oper_status"] = val
            elif oid.startswith(".1.3.6.1.2.1.31.1.1.1.6."):
                idx = oid.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["if_in_octets"] = val
            elif oid.startswith(".1.3.6.1.2.1.31.1.1.1.10."):
                idx = oid.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["if_out_octets"] = val
                
        for idx, fields in interfaces.items():
            if not fields: continue
            if_tags = base_tags.copy()
            if_name = fields.pop("if_name", str(idx))
            if_tags["if_name"] = if_name
            
            if fields:
                if_metric = {
                    "name": "interface",
                    "tags": if_tags,
                    "fields": fields,
                    "timestamp": timestamp
                }
                print(json.dumps(if_metric))
                
        storages = {}
        for oid, val in snmp_data.items():
            if oid.startswith(".1.3.6.1.2.1.25.2.3.1.3."):
                idx = oid.split(".")[-1]
                if idx not in storages: storages[idx] = {}
                storages[idx]["storageDescr"] = str(val)
            elif oid.startswith(".1.3.6.1.2.1.25.2.3.1.5."):
                idx = oid.split(".")[-1]
                if idx not in storages: storages[idx] = {}
                storages[idx]["storageSize"] = val
            elif oid.startswith(".1.3.6.1.2.1.25.2.3.1.6."):
                idx = oid.split(".")[-1]
                if str(idx) == "65536": continue
                if idx not in storages: storages[idx] = {}
                storages[idx]["storageUsed"] = val
            elif oid.startswith(".1.3.6.1.2.1.25.2.3.1.2."):
                idx = oid.split(".")[-1]
                if idx not in storages: storages[idx] = {}
                mapping = {
                    ".1.3.6.1.2.1.25.2.1.1": "Other",
                    ".1.3.6.1.2.1.25.2.1.2": "RAM",
                    ".1.3.6.1.2.1.25.2.1.3": "VirtualMemory",
                    ".1.3.6.1.2.1.25.2.1.4": "FixedDisk",
                    ".1.3.6.1.2.1.25.2.1.5": "RemovableDisk",
                    ".1.3.6.1.2.1.25.2.1.8": "RamDisk",
                    ".1.3.6.1.2.1.25.2.1.9": "FlashMemory",
                    ".1.3.6.1.2.1.25.2.1.10": "NetworkDisk"
                }
                val_str = str(val)
                if not val_str.startswith("."): val_str = "." + val_str
                storages[idx]["storage_type"] = mapping.get(val_str, str(val))

        for idx, fields in storages.items():
            if not fields: continue
            st_tags = base_tags.copy()
            st_descr = fields.pop("storageDescr", str(idx))
            st_tags["storageDescr"] = st_descr
            
            if fields:
                st_metric = {
                    "name": "dcim_network_storage",
                    "tags": st_tags,
                    "fields": fields,
                    "timestamp": timestamp
                }
                print(json.dumps(st_metric))

if __name__ == "__main__":
    main()
