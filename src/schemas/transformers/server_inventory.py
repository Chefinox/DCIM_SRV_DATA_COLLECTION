from datetime import datetime

SPEED_MAP = {10: 1, 100: 2, 1000: 3, 10000: 4, 25000: 7, 40000: 5, 100000: 6}

def transform_redfish_to_inventory(ip, raw_payloads):
    """
    Pure transformation: Converts raw Redfish responses into a flat DCIM inventory object.
    raw_payloads is a dict: {'systems': {...}, 'chassis': {...}, 'managers': {...}, ...}
    """
    sys_data = raw_payloads.get("systems", {})
    chassis_data = raw_payloads.get("chassis", {})
    mgr_data = raw_payloads.get("managers", {})

    # Extract System Name
    loc_name = chassis_data.get("Location", {}).get("PostalAddress", {}).get("Name")
    hostname = loc_name.strip() if loc_name else None

    result = {
        "ip": ip,
        "hostname": hostname,
        "serial_number": sys_data.get("SerialNumber"),
        "model": sys_data.get("Model"),
        "firmware": mgr_data.get("FirmwareVersion"),
        "bios_version": sys_data.get("BiosVersion"),
        "system_name": hostname,
        "processors": [],
        "memory": [],
        "ethernets": [],
        "disks": []
    }

    # Processors
    for p in raw_payloads.get("processors", []):
        if p and p.get("Status", {}).get("State") != "Absent":
            result["processors"].append({
                "model_name": p.get("Model"),
                "cores": p.get("TotalCores"),
                "logical_cores": p.get("TotalThreads"),
                "speed_mhz": p.get("MaxSpeedMHz")
            })

    # Memory
    for mem in raw_payloads.get("memory", []):
        if mem and (mem.get("CapacityMiB") or 0) > 0 and mem.get("Status", {}).get("State") != "Absent":
            result["memory"].append({
                "model_name": mem.get("VendorID") or mem.get("Manufacturer"),
                "size_mb": mem.get("CapacityMiB"),
                "speed_mhz": mem.get("OperatingSpeedMhz")
            })

    # Ethernets
    for e in raw_payloads.get("ethernets", []):
        if e and e.get("MACAddress") and e.get("Id") != "ToManager":
            result["ethernets"].append({
                "label": e.get("Id"),
                "mac": e.get("MACAddress"),
                "speed_gbps": SPEED_MAP.get(e.get("SpeedMbps", 0), 11),
                "model_name": e.get("Description") or "Ethernet Interface"
            })

    # Disks
    for d in raw_payloads.get("disks", []):
        if d and d.get("SerialNumber") and d.get("Status", {}).get("State") != "Absent":
            raw_slot = d.get("PhysicalLocation", {}).get("PartLocation", {}).get("LocationOrdinalValue") or d.get("Id")
            slot = str(raw_slot).replace("Disk.", "") if raw_slot is not None else None
            
            result["disks"].append({
                "model_name": d.get("Name") or d.get("Model"),
                "serial_number": d.get("SerialNumber"),
                "size_gb": int(d.get("CapacityBytes", 0) / (1024 ** 3)),
                "firmware_version": d.get("Revision"),
                "slot": slot
            })

    return result
