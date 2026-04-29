#!/usr/bin/env python3
import subprocess
import json
import urllib.request
import base64
import ssl
from datetime import datetime, timezone

# --- Configuration ---
PROXMOX_HOST = "10.50.0.11"
SSH_USER = "root"
SSH_PASS = "F!tech@0918"
ES_URL = "https://10.70.0.56:9200/server-ipmi-metrics-2026.04.10/_doc"
ES_USER = "elastic"
ES_PASS = "C+H+pFb*aIAqWcOo-X8q"

# --- Setup SSL Context for Self-Signed ES ---
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def run_ipmi_over_ssh():
    # Execute ipmitool locally on the Proxmox host using sshpass
    cmd = [
        "sshpass", "-p", SSH_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no", f"{SSH_USER}@{PROXMOX_HOST}",
        "ipmitool sdr list -c"  # -c outputs CSV format for easy parsing
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if result.returncode != 0:
            print(f"SSH/IPMI Error: {result.stderr}")
            return None
        return result.stdout.strip().split('\n')
    except Exception as e:
        print(f"Execution Error: {e}")
        return None

def parse_sdr_csv(lines):
    parsed = {}
    for line in lines:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 3:
            sensor_name = parts[0]
            val = parts[1]
            unit = parts[2]
            
            # Skip invalid readings
            if val.lower() in ["ns", "na", "no reading"]:
                continue
                
            try:
                # Format name safely for ES keys
                key = sensor_name.replace(" ", "_").replace(".", "_").replace("+", "plus").replace("-", "minus")
                parsed[f"{key}_{unit}"] = float(val)
            except ValueError:
                # If value is not float, treat as string status (e.g., 'ok')
                key = sensor_name.replace(" ", "_")
                parsed[f"{key}_Status"] = val
    return parsed

def push_to_es(metrics):
    if not metrics:
        return
        
    payload = {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "measurement_name": "server_ipmi",
        "tag": {
            "host": "server-Render-01",
            "proxmox_node": PROXMOX_HOST
        },
        "server_ipmi": metrics
    }
    
    auth = base64.b64encode(f"{ES_USER}:{ES_PASS}".encode()).decode()
    req = urllib.request.Request(
        ES_URL, 
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}"
        }
    )
    
    try:
        urllib.request.urlopen(req, context=ctx)
        print(f"Successfully pushed {len(metrics)} IPMI metrics to ES.")
    except Exception as e:
        print(f"ES Error: {e}")

if __name__ == "__main__":
    raw_lines = run_ipmi_over_ssh()
    if raw_lines:
        metrics = parse_sdr_csv(raw_lines)
        push_to_es(metrics)
