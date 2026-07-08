#!/usr/bin/env python3
import sys
import json
import time
import subprocess

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
        "snmpwalk", "-Oqn", "-v3", 
        "-l", "authNoPriv", 
        "-u", "hndept", 
        "-a", "SHA", 
        "-A", "F!tech0918", 
        "-t", "2", "-r", "1", 
        ip, oid
    ]
    snmp_data = {}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                o = parts[0]
                if not o.startswith("."):
                    o = "." + o
                snmp_data[o] = parse_value(parts[1])
    except Exception as e:
        sys.stderr.write(f"Error polling {ip} at {oid}: {e}\n")
    return snmp_data

def main():
    timestamp = int(time.time())
    
    for ip in IPS:
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
                    fields[name] = data[oid]
                else:
                    base_tags[name] = str(data[oid])
                    
        # Always output nas global metrics if anything responded
        if len(base_tags) > 2 or fields:
            print(json.dumps({
                "name": "nas_snmp",
                "tags": base_tags,
                "fields": fields if fields else {"status": 1},
                "timestamp": timestamp
            }))
            
        # 2. Disk Table
        disk_data = snmp_walk(ip, ".1.3.6.1.4.1.6574.2.1.1")
        disks = {}
        for o, v in disk_data.items():
            if o.startswith(".1.3.6.1.4.1.6574.2.1.1.2."): # diskID
                idx = o.split(".")[-1]
                if idx not in disks: disks[idx] = {}
                disks[idx]["diskID"] = str(v)
            elif o.startswith(".1.3.6.1.4.1.6574.2.1.1.3."): # diskModel
                idx = o.split(".")[-1]
                if idx not in disks: disks[idx] = {}
                disks[idx]["diskModel"] = str(v)
            elif o.startswith(".1.3.6.1.4.1.6574.2.1.1.5."): # diskStatus
                idx = o.split(".")[-1]
                if idx not in disks: disks[idx] = {}
                disks[idx]["diskStatus"] = v
            elif o.startswith(".1.3.6.1.4.1.6574.2.1.1.6."): # diskTemp
                idx = o.split(".")[-1]
                if idx not in disks: disks[idx] = {}
                disks[idx]["diskTemp"] = v
                
        for idx, flds in disks.items():
            if not flds: continue
            d_tags = base_tags.copy()
            if "diskID" in flds:
                d_tags["diskID"] = flds.pop("diskID")
            else:
                d_tags["diskID"] = str(idx)
                
            if flds:
                print(json.dumps({
                    "name": "dcim_nas",
                    "tags": d_tags,
                    "fields": flds,
                    "timestamp": timestamp
                }))
                
        # 3. Volume Table
        vol_data = snmp_walk(ip, ".1.3.6.1.4.1.6574.3.1.1")
        vols = {}
        for o, v in vol_data.items():
            if o.startswith(".1.3.6.1.4.1.6574.3.1.1.2."):
                idx = o.split(".")[-1]
                if idx not in vols: vols[idx] = {}
                vols[idx]["volumeName"] = str(v)
            elif o.startswith(".1.3.6.1.4.1.6574.3.1.1.3."):
                idx = o.split(".")[-1]
                if idx not in vols: vols[idx] = {}
                vols[idx]["volumeStatus"] = v
            elif o.startswith(".1.3.6.1.4.1.6574.3.1.1.5."):
                idx = o.split(".")[-1]
                if idx not in vols: vols[idx] = {}
                vols[idx]["volumeTotalBytes"] = v
            elif o.startswith(".1.3.6.1.4.1.6574.3.1.1.4."):
                idx = o.split(".")[-1]
                if idx not in vols: vols[idx] = {}
                vols[idx]["volumeUsedBytes"] = v
                
        for idx, flds in vols.items():
            if not flds: continue
            v_tags = base_tags.copy()
            if "volumeName" in flds:
                v_tags["volumeName"] = flds.pop("volumeName")
            else:
                v_tags["volumeName"] = str(idx)
                
            if flds:
                print(json.dumps({
                    "name": "dcim_nas_volume",
                    "tags": v_tags,
                    "fields": flds,
                    "timestamp": timestamp
                }))
                
        # 4. Interface Table
        if_data = snmp_walk(ip, ".1.3.6.1.2.1.2.2.1")
        if_data.update(snmp_walk(ip, ".1.3.6.1.2.1.31.1.1.1"))
        
        interfaces = {}
        for o, v in if_data.items():
            if o.startswith(".1.3.6.1.2.1.2.2.1.1."):
                idx = o.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["ifIndex"] = str(v)
            elif o.startswith(".1.3.6.1.2.1.2.2.1.2.") or o.startswith(".1.3.6.1.2.1.31.1.1.1.1."):
                idx = o.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["ifName"] = str(v)
            elif o.startswith(".1.3.6.1.2.1.2.2.1.8."):
                idx = o.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["ifOperStatus"] = v
            elif o.startswith(".1.3.6.1.2.1.31.1.1.1.6."):
                idx = o.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["ifHCInOctets"] = v
            elif o.startswith(".1.3.6.1.2.1.31.1.1.1.10."):
                idx = o.split(".")[-1]
                if idx not in interfaces: interfaces[idx] = {}
                interfaces[idx]["ifHCOutOctets"] = v
                
        for idx, flds in interfaces.items():
            if not flds: continue
            i_tags = base_tags.copy()
            if "ifName" in flds:
                i_tags["ifName"] = flds.pop("ifName")
            elif "ifIndex" in flds:
                i_tags["ifIndex"] = flds.pop("ifIndex")
            else:
                i_tags["ifIndex"] = str(idx)
                
            if flds:
                print(json.dumps({
                    "name": "interface",
                    "tags": i_tags,
                    "fields": flds,
                    "timestamp": timestamp
                }))

if __name__ == "__main__":
    main()
