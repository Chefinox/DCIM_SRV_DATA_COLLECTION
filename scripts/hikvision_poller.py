import requests
import json
import datetime
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth
import urllib3
import os
from dotenv import load_dotenv

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

# Configuration
NVR_IP = "192.168.1.254"
CCTV_IPS = [
    "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5", "192.168.1.6",
    "192.168.1.7", "192.168.1.8", "192.168.1.9", "192.168.1.10", "192.168.1.11",
    "192.168.1.12", "192.168.1.14", "192.168.1.15", "192.168.1.19", "192.168.1.24",
    "192.168.1.25", "192.168.1.26", "192.168.1.27", "192.168.1.28", "192.168.1.29",
    "192.168.1.30", "192.168.1.31", "192.168.1.33"
]

# CCTV Credentials
DEVICE_USER = os.getenv("HIKVISION_CAM_USER", "admin")
DEVICE_PASS = os.getenv("HIKVISION_CAM_PASS", "qRvbi883=Zk[Q)@5")

# NVR Credentials
NVR_USER = os.getenv("HIKVISION_NVR_USER", "admin")
NVR_PASS = os.getenv("HIKVISION_NVR_PASS", "qRvbi883=Zk[Q)@5")

def get_isapi(ip, path, user, password):
    url = f"http://{ip}/ISAPI{path}"
    try:
        response = requests.get(url, auth=HTTPDigestAuth(user, password), timeout=5)
        if response.status_code == 200:
            return response.text
        if response.status_code == 401:
            response = requests.get(url, auth=(user, password), timeout=5)
            if response.status_code == 200:
                return response.text
        return None
    except:
        return None

def parse_xml_to_dict(xml_node):
    if isinstance(xml_node, str):
        try:
            xml_node = ET.fromstring(xml_node)
        except:
            return {}
    data = {}
    for child in xml_node:
        tag = child.tag.split('}')[-1]
        if len(child) > 0:
            child_data = parse_xml_to_dict(child)
        else:
            child_data = child.text.strip() if child.text else ""
        if tag in data:
            if not isinstance(data[tag], list):
                data[tag] = [data[tag]]
            data[tag].append(child_data)
        else:
            data[tag] = child_data
    return data

def metrics_to_influx_line(metrics):
    """Convert metrics dict to InfluxDB Line Protocol for Telegraf to consume."""
    measurement = "cctv_metrics"
    
    # Build tags
    tags = {
        "hostname":      metrics.get("hostname", "unknown").replace(" ", "_"),
        "serial_number": metrics.get("serial_number", "NO_SN").replace(" ", "_"),
        "ip":            metrics.get("ip", ""),
        "model":         metrics.get("model", "unknown").replace(" ", "_"),
        "firmware":      metrics.get("firmware", "").replace(" ", "_"),
        "device_type":   str(metrics.get("device_type", "cctv")).lower(),
    }
    tag_str = ",".join(f"{k}={v}" for k, v in tags.items() if v)

    # Build fields
    status_val = 1 if metrics.get("status") == "Online" else 0
    fields = {
        "status_online": status_val,
        "status_text":   f'"{metrics.get("status", "Offline")}"'
    }
    
    # Add optional detail metrics if online
    if status_val == 1:
        # Example utilization from NVR if available
        sys_stats = metrics.get("system_status", {})
        cpu = sys_stats.get("CPUList", {}).get("CPU", {}).get("cpuUtilization")
        if cpu:
            fields["cpuUtilization"] = cpu
        mem = sys_stats.get("MemoryList", {}).get("Memory", {}).get("memoryUsage")
        if mem:
            fields["memoryUsage"] = mem

    field_str = ",".join(f"{k}={v}" for k, v in fields.items())

    # Timestamp (Telegraf will add its own if omitted, but let's provide ns)
    ts_ns = int(datetime.datetime.utcnow().timestamp() * 1e9)
    return f"{measurement},{tag_str} {field_str} {ts_ns}"

def poll_device(ip, user, password, device_type="CCTV"):
    metrics = {
        "category": "security",
        "device_type": device_type,
        "ip": ip,
        "status": "Offline"
    }

    info_xml = get_isapi(ip, "/System/deviceInfo", user, password)
    if info_xml:
        metrics["status"] = "Online"
        di = parse_xml_to_dict(info_xml)
        metrics["model"] = di.get("model", "")
        metrics["serial_number"] = di.get("serialNumber", "")
        metrics["hostname"] = di.get("deviceName", "")
        metrics["firmware"] = di.get("firmwareVersion", "")
        
        status_xml = get_isapi(ip, "/System/status", user, password)
        if status_xml:
            metrics["system_status"] = parse_xml_to_dict(status_xml)
    return metrics

def main():
    # Poll NVR
    nvr_m = poll_device(NVR_IP, NVR_USER, NVR_PASS, "NVR")
    print(metrics_to_influx_line(nvr_m))

    # Poll Cameras
    for ip in CCTV_IPS:
        cam_m = poll_device(ip, DEVICE_USER, DEVICE_PASS, "CCTV")
        print(metrics_to_influx_line(cam_m))

if __name__ == "__main__":
    main()
