import xml.etree.ElementTree as ET
import re

UNKNOWN_VALUES = {"", "unknown", "none", "null", "NO_SN", "NO_IDENTIFIER"}

def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value and value not in UNKNOWN_VALUES and value.lower() not in UNKNOWN_VALUES else None

def _fallback_hostname(ip):
    return f"CCTV-{str(ip).replace('.', '-')}"

def _fallback_serial(ip):
    return f"CCTV-IP-{ip}"

def parse_isapi_xml(xml_string):
    """Recursively converts ISAPI XML responses to Python dictionaries."""
    if not xml_string:
        return {}
    try:
        # Strip namespaces for cleaner parsing
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', xml_string)
        root = ET.fromstring(clean_xml)
        return _xml_to_dict(root)
    except Exception:
        return {}

def _xml_to_dict(node):
    data = {}
    for child in node:
        tag = child.tag.split('}')[-1]
        if len(child) > 0:
            child_data = _xml_to_dict(child)
        else:
            child_data = child.text.strip() if child.text else ""
        
        if tag in data:
            if not isinstance(data[tag], list):
                data[tag] = [data[tag]]
            data[tag].append(child_data)
        else:
            data[tag] = child_data
    return data

def transform_to_cctv_metrics(ip, device_info, sys_status=None, storage_status=None):
    """Normalizes Hikvision data into a standard CCTV metrics dict."""
    model = _clean(device_info.get("model")) or "DS-2CD"
    
    # Process Storage (HDD) metrics
    capacity = 0
    free_space = 0
    hdd_status = "ok"
    
    if storage_status and "hdd" in storage_status:
        hdds = storage_status.get("hdd", [])
        if not isinstance(hdds, list):
            hdds = [hdds]
        
        for hdd in hdds:
            if hdd.get("capacity"):
                capacity += int(hdd.get("capacity", 0))
            if hdd.get("freeSpace"):
                free_space += int(hdd.get("freeSpace", 0))
            
            stat = str(hdd.get("status", "ok")).lower()
            if stat not in ("ok", "idle"):
                hdd_status = stat
                
    capacity_gb = round(capacity / 1024.0, 2) if capacity > 0 else None
    free_space_gb = round(free_space / 1024.0, 2) if capacity > 0 else None

    return {
        "hostname":      _clean(device_info.get("deviceName")) or _fallback_hostname(ip),
        "serial_number": _clean(device_info.get("serialNumber")) or _fallback_serial(ip),
        "ip":            ip,
        "manufacturer":  "Hikvision" if model.upper().startswith("DS-") else "Unknown",
        "model":         model,
        "firmware":      device_info.get("firmwareVersion", ""),
        "device_type":   "cctv",
        "status":        "Online" if device_info else "Offline",
        "utilization": {
            "cpu": sys_status.get("CPUList", {}).get("CPU", {}).get("cpuUtilization") if sys_status else None,
            "memory": sys_status.get("MemoryList", {}).get("Memory", {}).get("memoryUsage") if sys_status else None,
            "memory_available": sys_status.get("MemoryList", {}).get("Memory", {}).get("memoryAvailable") if sys_status else None
        },
        "storage": {
            "capacity": capacity_gb,
            "freeSpace": free_space_gb,
            "status": hdd_status if capacity else None
        }
    }
