#!/usr/bin/env python3
import sys
import json
import time

def parse_value(val_str):
    if val_str is None: return None
    try:
        return int(val_str)
    except ValueError:
        pass
    try:
        return float(val_str)
    except ValueError:
        pass
    return val_str.strip()

def main():
    try:
        raw_data = sys.stdin.read()
        if not raw_data.strip():
            return
            
        data = json.loads(raw_data)
        
        snmp_data = {}
        ip = "unknown"
        
        for k, v in data.items():
            if k == "agent_host" or k == "ip":
                ip = v
            if k.startswith("snmp$"):
                parts = k.split("$")
                if len(parts) >= 2:
                    oid = parts[1]
                    if not oid.startswith("."):
                        oid = "." + oid
                    snmp_data[oid] = parse_value(v)
                    
        for k, v in data.items():
            if k.startswith("snmp$peerAddress"):
                ip = v.split("/")[0]

        timestamp = int(time.time())
        
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
                
    except Exception as e:
        sys.stderr.write(f"Error parsing NiFi SNMP data: {e}\n")

if __name__ == "__main__":
    main()
