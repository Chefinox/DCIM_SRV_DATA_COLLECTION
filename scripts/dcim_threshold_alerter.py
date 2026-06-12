#!/usr/bin/env python3
"""DCIM Threshold Alerter Service.

Periodically queries Elasticsearch for metrics that exceed defined thresholds.
Logs alerts to:
  1. Log file: /home/infra/dcim_metrics_project/logs/threshold_alerts.log
  2. Elasticsearch index: dcim-alerts (for Kibana visualization)

No license required - uses standard ES search API.

Thresholds:
  - Server Temperature > 75°C (Critical)
  - UPS Battery < 50% (Warning)
  - UPS Load > 80% (Warning)
  - NAS Disk Temperature > 55°C (Warning)
  - NVR Memory Usage > 90% (Warning)
  - Network Switch CPU > 85% (Warning)
"""
import time
import json
import logging
import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger
import requests
from datetime import datetime, timezone
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIG ---
ES_URL = "https://10.70.0.56:9200"
ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
ES_HEADERS = {"Content-Type": "application/json"}
ALERT_INDEX = "dcim-alerts"
CHECK_INTERVAL = 120  # seconds (2 minutes)
LOOKBACK = "5m"

LOG_FILE = "/home/infra/dcim_metrics_project/logs/threshold_alerts.log"
logging = setup_logger("dcim-threshold-alerter", LOG_FILE)

# --- THRESHOLD DEFINITIONS ---
THRESHOLDS = [
    {
        "id": "server-temp-critical",
        "description": "Server Temperature >75°C",
        "device_type": "server",
        "field": "raw_fields.srv_reading_celsius",
        "comparator": "gt",
        "threshold": 75,
        "severity": "critical",
        "agg": "max"
    },
    {
        "id": "ups-battery-low",
        "description": "UPS Battery <50%",
        "device_type": "ups",
        "field": "raw_fields.battery_capacity",
        "comparator": "lt",
        "threshold": 50,
        "severity": "warning",
        "agg": "min"
    },
    {
        "id": "ups-load-high",
        "description": "UPS Load >80%",
        "device_type": "ups",
        "field": "raw_fields.output_load",
        "comparator": "gt",
        "threshold": 80,
        "severity": "warning",
        "agg": "max"
    },
    {
        "id": "nas-disk-temp-high",
        "description": "NAS Disk Temp >55°C",
        "device_type": "nas",
        "field": "raw_fields.diskTemp",
        "comparator": "gt",
        "threshold": 55,
        "severity": "warning",
        "agg": "max"
    },
    {
        "id": "nvr-memory-high",
        "description": "NVR Memory >90%",
        "device_type": "nvr",
        "field": "raw_fields.memoryUsagePct",
        "comparator": "gt",
        "threshold": 90,
        "severity": "warning",
        "agg": "max"
    },
    {
        "id": "network-cpu-high",
        "description": "Network Switch CPU >85%",
        "device_type": "network_switch",
        "field": "raw_fields.cpu_load",
        "comparator": "gt",
        "threshold": 85,
        "severity": "warning",
        "agg": "max"
    },
]


def check_threshold(rule):
    """Query ES and check if threshold is breached."""
    query = {
        "size": 0,
        "query": {
            "bool": {
                "must": [
                    {"term": {"device_type.keyword": rule["device_type"]}},
                    {"exists": {"field": rule["field"]}},
                    {"range": {"@timestamp": {"gte": f"now-{LOOKBACK}"}}}
                ]
            }
        },
        "aggs": {
            "check": {rule["agg"]: {"field": rule["field"]}},
            "per_host": {
                "terms": {"field": "hostname.keyword", "size": 10},
                "aggs": {
                    "val": {rule["agg"]: {"field": rule["field"]}}
                }
            }
        }
    }

    try:
        r = requests.get(f"{ES_URL}/dcim-metrics-unified-*/_search",
                         auth=ES_AUTH, headers=ES_HEADERS, json=query, verify=False, timeout=10)
        if not r.ok:
            return None

        data = r.json()
        value = data["aggregations"]["check"]["value"]
        if value is None:
            return None

        # Check if threshold breached
        breached = False
        if rule["comparator"] == "gt" and value > rule["threshold"]:
            breached = True
        elif rule["comparator"] == "lt" and value < rule["threshold"]:
            breached = True

        if breached:
            # Find affected hosts
            affected = []
            for bucket in data["aggregations"]["per_host"]["buckets"]:
                host_val = bucket["val"]["value"]
                if host_val is not None:
                    if rule["comparator"] == "gt" and host_val > rule["threshold"]:
                        affected.append({"hostname": bucket["key"], "value": host_val})
                    elif rule["comparator"] == "lt" and host_val < rule["threshold"]:
                        affected.append({"hostname": bucket["key"], "value": host_val})

            return {
                "alert_id": rule["id"],
                "alert_name": rule["description"],
                "severity": rule["severity"],
                "device_type": rule["device_type"],
                "metric_field": rule["field"],
                "threshold": rule["threshold"],
                "current_value": value,
                "affected_hosts": affected,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    except Exception as e:
        logging.error(f"Error checking {rule['id']}: {e}")

    return None


def index_alert(alert):
    """Write alert to ES index for Kibana visualization."""
    try:
        r = requests.post(f"{ES_URL}/{ALERT_INDEX}/_doc",
                          auth=ES_AUTH, headers=ES_HEADERS,
                          json=alert, verify=False, timeout=5)
        if not r.ok:
            logging.warning(f"Failed to index alert: {r.status_code}")
    except Exception as e:
        logging.warning(f"Failed to index alert: {e}")


# --- STALE DEVICE DETECTION ---
KNOWN_DEVICES = {
    "server": ["SRV-Render-01", "SRV-Render-02", "SRV-HCI-01", "SRV-HCI-02", "SRV-HCI-03"],
    "ups": ["UPS-FIT"],
    "nas": ["NAS-FIT", "NAS-INFRA", "NAS-FAT", "NAS-SD01", "NAS-CD01", "NAS-CD02"],
    "network_switch": ["FIT-Core-SW", "FIT-Core-RTR", "FIT-DIST-SW-SERVER1", "FIT-DIST-SW-SERVER2", "FIT-DIST-SW-LAN1"],
    "nvr": ["NVR-FIT"],
}
STALE_THRESHOLD_MINUTES = 30  # Alert if no data for 30 min


def check_stale_devices():
    """Detect devices that stopped sending data (possible decommission/failure)."""
    stale_alerts = []

    for device_type, expected_hosts in KNOWN_DEVICES.items():
        try:
            r = requests.get(f"{ES_URL}/dcim-metrics-unified-*/_search",
                             auth=ES_AUTH, headers=ES_HEADERS, verify=False, timeout=10,
                             json={
                                 "size": 0,
                                 "query": {"bool": {"must": [
                                     {"term": {"device_type.keyword": device_type}},
                                     {"range": {"@timestamp": {"gte": f"now-{STALE_THRESHOLD_MINUTES}m"}}}
                                 ]}},
                                 "aggs": {
                                     "active_hosts": {
                                         "terms": {"field": "hostname.keyword", "size": 50}
                                     }
                                 }
                             })
            if not r.ok:
                continue

            data = r.json()
            active = {b["key"] for b in data["aggregations"]["active_hosts"]["buckets"]}
            missing = [h for h in expected_hosts if h not in active]

            if missing:
                alert = {
                    "alert_id": f"stale-{device_type}",
                    "alert_name": f"Device Not Reporting ({device_type})",
                    "severity": "warning",
                    "device_type": device_type,
                    "metric_field": "last_seen",
                    "threshold": STALE_THRESHOLD_MINUTES,
                    "current_value": len(missing),
                    "affected_hosts": [{"hostname": h, "value": f"no data >{STALE_THRESHOLD_MINUTES}m"} for h in missing],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                stale_alerts.append(alert)

        except Exception as e:
            logging.error(f"Error checking stale {device_type}: {e}")

    return stale_alerts


def run():
    logging.info("=== DCIM Threshold Alerter Started ===")
    logging.info(f"Checking {len(THRESHOLDS)} thresholds + stale device detection every {CHECK_INTERVAL}s")
    logging.info(f"Lookback window: {LOOKBACK} | Stale threshold: {STALE_THRESHOLD_MINUTES}m")

    while True:
        alerts_fired = 0

        # Threshold checks
        for rule in THRESHOLDS:
            alert = check_threshold(rule)
            if alert:
                alerts_fired += 1
                hosts_str = ", ".join([f"{h['hostname']}={h['value']}" for h in alert["affected_hosts"]])
                logging.warning(
                    f"[{alert['severity'].upper()}] {alert['alert_name']} | "
                    f"value={alert['current_value']} threshold={alert['threshold']} | "
                    f"hosts: {hosts_str}"
                )
                index_alert(alert)

        # Stale device checks
        stale_alerts = check_stale_devices()
        for alert in stale_alerts:
            alerts_fired += 1
            missing_str = ", ".join([h["hostname"] for h in alert["affected_hosts"]])
            logging.warning(
                f"[{alert['severity'].upper()}] {alert['alert_name']} | "
                f"missing: {missing_str} (>{STALE_THRESHOLD_MINUTES}m no data)"
            )
            index_alert(alert)

        if alerts_fired == 0:
            logging.info(f"All clear - {len(THRESHOLDS)} thresholds + stale check passed")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run()
