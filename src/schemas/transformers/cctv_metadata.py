import xml.etree.ElementTree as ET
import re

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

def transform_to_cctv_metrics(ip, device_info, sys_status=None):
    """Normalizes Hikvision data into a standard CCTV metrics dict."""
    return {
        "hostname":      device_info.get("deviceName", "unknown"),
        "serial_number": device_info.get("serialNumber", "NO_SN"),
        "ip":            ip,
        "model":         device_info.get("model", "unknown"),
        "firmware":      device_info.get("firmwareVersion", ""),
        "device_type":   "cctv",
        "status":        "Online" if device_info else "Offline",
        "utilization": {
            "cpu": sys_status.get("CPUList", {}).get("CPU", {}).get("cpuUtilization") if sys_status else None,
            "memory": sys_status.get("MemoryList", {}).get("Memory", {}).get("memoryUsage") if sys_status else None
        }
    }
