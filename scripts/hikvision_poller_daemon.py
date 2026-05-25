#!/usr/bin/env python3
"""
CCTV Poller Daemon - Continuous monitoring service
Polls CCTV cameras every 120 seconds and sends metrics to Kafka
"""
import sys
import os
import time
import logging
import json
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.skills.security.cctv_poller.executor import CCTVPollerExecutor
from src.tools.messaging.kafka_client import KafkaClient

# --- CONFIGURATION ---
load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

POLL_INTERVAL = 120  # seconds (2 minutes)
KAFKA_TOPIC = "dcim.raw.device.isapi"

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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Kafka producer
kafka_client = KafkaClient()
producer = None

def format_to_influx_json(metrics, category):
    ip = metrics.get("ip") or ""
    hostname = metrics.get("hostname") or f"CCTV-{str(ip).replace('.', '-')}"
    serial_number = metrics.get("serial_number")
    if not serial_number or serial_number in ("NO_SN", "NO_IDENTIFIER", "unknown"):
        serial_number = f"CCTV-IP-{str(ip).replace('.', '-')}"
    model = metrics.get("model") or "DS-2CD"
    manufacturer = metrics.get("manufacturer") or "Hikvision"
    device_type = category.lower()  # "nvr" or "cctv"
    
    tags = {
        "hostname": hostname,
        "serial_number": serial_number,
        "ip": ip,
        "model": model,
        "manufacturer": manufacturer,
        "device_type": device_type
    }
    
    status_val = 1 if metrics.get("status") == "Online" else 0
    fields = {
        "status_online": status_val,
        "status_text": metrics.get("status", "Offline")
    }
    
    util = metrics.get("utilization", {})
    if util.get("cpu") is not None: fields["cpuUtilization"] = util["cpu"]
    if util.get("memory") is not None: fields["memoryUsage"] = util["memory"]
    if util.get("memory_available") is not None: fields["memoryAvailable"] = util["memory_available"]
    
    ts_ns = int(time.time() * 1e9)
    
    return {
        "name": "cctv_metrics",
        "tags": tags,
        "fields": fields,
        "timestamp": ts_ns
    }

def poll_once():
    """Execute one polling cycle"""
    global producer
    
    try:
        executor = CCTVPollerExecutor()
        
        # Initialize Kafka producer if not exists
        if producer is None:
            logger.info("Initializing Kafka producer...")
            producer = kafka_client.get_producer()
        
        # 1. Poll NVR
        logger.info(f"Polling NVR at {NVR_IP}")
        nvr_metrics = executor.poll_device(NVR_IP, NVR_USER, NVR_PASS, "NVR")
        
        # Wrap NVR metrics in Influx JSON format
        nvr_influx = format_to_influx_json(nvr_metrics, "NVR")
        producer.send(KAFKA_TOPIC, value=nvr_influx)

        # 2. Get Proxy Mapping from NVR
        cam_mapping = executor.discover_nvr_channels(NVR_IP, NVR_USER, NVR_PASS)
        logger.info(f"Discovered {len(cam_mapping)} cameras from NVR")

        # 3. Poll Cameras
        online_count = 0
        offline_count = 0
        
        for ip in CCTV_IPS:
            cam_metrics = executor.poll_device(ip, DEVICE_USER, DEVICE_PASS, "CCTV")
            
            # Fallback to NVR mapping if device is offline, unauthorized, or placeholder
            is_placeholder = (
                not cam_metrics.get("serial_number") or
                cam_metrics["serial_number"].startswith("CCTV-IP-") or
                cam_metrics["serial_number"] in ("NO_SN", "NO_IDENTIFIER", "unknown")
            )
            if is_placeholder and ip in cam_mapping:
                cam_info = cam_mapping[ip]
                logger.info(f"Using NVR mapping fallback for IP {ip}: Real SN {cam_info['serial_number']}")
                cam_metrics["serial_number"] = cam_info["serial_number"]
                if cam_info.get("model"):
                    cam_metrics["model"] = cam_info["model"]
                if cam_info.get("firmware"):
                    cam_metrics["firmware"] = cam_info["firmware"]
                if cam_info.get("hostname"):
                    cam_metrics["hostname"] = cam_info["hostname"]
            
            if cam_metrics.get("status") == "Online":
                online_count += 1
            else:
                offline_count += 1
            
            # Wrap in Influx JSON format and send to Kafka
            cam_influx = format_to_influx_json(cam_metrics, "CCTV")
            producer.send(KAFKA_TOPIC, value=cam_influx)
        
        # Flush producer to ensure all messages sent
        producer.flush()
        
        logger.info(f"Polling complete: {online_count} online, {offline_count} offline (total: {len(CCTV_IPS)} cameras)")
        logger.info(f"Sent {len(CCTV_IPS) + 1} messages to Kafka topic: {KAFKA_TOPIC}")
        return True
        
    except Exception as e:
        logger.error(f"Polling cycle failed: {e}", exc_info=True)
        return False

def main():
    """Main daemon loop"""
    global producer
    
    logger.info("=" * 60)
    logger.info("DCIM CCTV Poller Daemon Starting")
    logger.info(f"Poll Interval: {POLL_INTERVAL} seconds")
    logger.info(f"Kafka Topic: {KAFKA_TOPIC}")
    logger.info(f"NVR: {NVR_IP}")
    logger.info(f"Cameras: {len(CCTV_IPS)} devices")
    logger.info("=" * 60)
    
    cycle_count = 0
    
    try:
        while True:
            try:
                cycle_count += 1
                start_time = time.time()
                
                logger.info(f"Starting polling cycle #{cycle_count} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                success = poll_once()
                
                elapsed = time.time() - start_time
                logger.info(f"Cycle #{cycle_count} completed in {elapsed:.2f}s (success={success})")
                
                # Sleep until next cycle
                logger.info(f"Sleeping for {POLL_INTERVAL} seconds until next cycle...")
                time.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal, exiting gracefully...")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                logger.info(f"Waiting {POLL_INTERVAL} seconds before retry...")
                time.sleep(POLL_INTERVAL)
    finally:
        # Cleanup
        if producer:
            logger.info("Closing Kafka producer...")
            producer.close()
        logger.info("DCIM CCTV Poller Daemon Stopped")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
