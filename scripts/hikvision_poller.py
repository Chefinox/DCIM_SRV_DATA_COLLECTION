#!/usr/bin/env python3
import sys
import os
import logging
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.skills.security.cctv_poller.executor import CCTVPollerExecutor
from src.schemas.output.influx_formatter import format_cctv_to_influx

# --- CONFIGURATION ---
load_dotenv('/home/infra/dcim_metrics_project/configs/.env')
NVR_IP = "192.168.1.254"
CCTV_IPS = [
    "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5", "192.168.1.6",
    "192.168.1.7", "192.168.1.8", "192.168.1.9", "192.168.1.10", "192.168.1.11",
    "192.168.1.12", "192.168.1.13", "192.168.1.14", "192.168.1.15", "192.168.1.16",
    "192.168.1.17", "192.168.1.18", "192.168.1.19", "192.168.1.20", "192.168.1.21",
    "192.168.1.22", "192.168.1.23", "192.168.1.24", "192.168.1.25", "192.168.1.26",
    "192.168.1.27", "192.168.1.28", "192.168.1.29", "192.168.1.30", "192.168.1.31",
    "192.168.1.33"  # Total: 31 units (192.168.1.2-33, skip .32)
]

DEVICE_USER = os.getenv("HIKVISION_CAM_USER", "admin")
DEVICE_PASS = os.getenv("HIKVISION_CAM_PASS", "F!tech0918")
NVR_USER = os.getenv("HIKVISION_NVR_USER", "admin")
NVR_PASS = os.getenv("HIKVISION_NVR_PASS", "qRvbi883=Zk[Q)@5")

def main():
    executor = CCTVPollerExecutor()
    
    # 1. Poll NVR
    nvr_metrics = executor.poll_device(NVR_IP, NVR_USER, NVR_PASS, "NVR")
    print(format_cctv_to_influx(nvr_metrics))

    # 2. Get Proxy Mapping from NVR
    cam_mapping = executor.discover_nvr_channels(NVR_IP, NVR_USER, NVR_PASS)

    # 3. Poll Cameras
    for ip in CCTV_IPS:
        cam_metrics = executor.poll_device(ip, DEVICE_USER, DEVICE_PASS, "CCTV")
        
        # Fallback to NVR mapping if device is offline or unauthorized
        if str(cam_metrics.get("serial_number", "")).startswith("CCTV-IP-") and ip in cam_mapping:
            cam_metrics["serial_number"] = cam_mapping[ip].get("serial_number", cam_metrics["serial_number"])
            
        print(format_cctv_to_influx(cam_metrics))

if __name__ == "__main__":
    main()
