#!/usr/bin/env python3
import requests
import urllib3
import json
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SERVERS = [
    {"ip": "10.50.0.2", "host": "server-HCI-01", "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.3", "host": "server-HCI-02", "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.4", "host": "server-HCI-03", "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.5", "host": "server-Render-01", "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.6", "host": "server-Render-02", "user": "root", "pass": "F!tech@0918"}
]

def get_metric_value(server, endpoint):
    url = f"https://{server['ip']}/redfish/v1/Systems/1/Oem/Lenovo/Metrics/{endpoint}"
    try:
        resp = requests.get(url, auth=(server["user"], server["pass"]), verify=False, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            container = data.get("Container", [])
            if container and len(container) > 0:
                return container[0].get("MetricValue")
    except Exception:
        pass
    return None

def poll_server(server):
    cpu = get_metric_value(server, "CPUSubsystemPerformance")
    mem = get_metric_value(server, "MemorySubsystemPerformance")
    
    if cpu is not None and mem is not None:
        line = f"server_redfish_util,hostname={server['host']} cpu_utilization={cpu},memory_usage={mem}"
    elif cpu is not None:
        line = f"server_redfish_util,hostname={server['host']} cpu_utilization={cpu}"
    elif mem is not None:
        line = f"server_redfish_util,hostname={server['host']} memory_usage={mem}"
    else:
        return
        
    print(line)

if __name__ == "__main__":
    import sys
    try:
        for s in SERVERS:
            poll_server(s)
        sys.stdout.flush()
    except Exception as e:
        pass
