#!/usr/bin/env python3
"""
Circuit Breaker Monitoring Script for Prometheus Textfile Collector.
Generates metrics for circuit breaker state & failure metrics.
"""

import os
import sys
import time
import json

if "/home/infra/dcim_metrics_project" not in sys.path:
    sys.path.append("/home/infra/dcim_metrics_project")

PROM_FILE_PATH = "/tmp/dcim_circuit_breaker.prom"

# Services to monitor from logs/circuit_breaker.log or live instances
LOG_FILE = "/home/infra/dcim_metrics_project/logs/circuit_breaker.log"

def parse_latest_states():
    """Parse circuit_breaker.log to extract the latest state per service."""
    services = {
        "itop": {"state": 0, "failures": 0, "last_change": 0},
        "redis": {"state": 0, "failures": 0, "last_change": 0},
        "elasticsearch": {"state": 0, "failures": 0, "last_change": 0},
    }

    state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}

    if not os.path.exists(LOG_FILE):
        return services

    try:
        with open(LOG_FILE, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    msg = record.get("message", "")
                    if "[CIRCUIT BREAKER]" in msg:
                        # Extract service name and state
                        # Example: [CIRCUIT BREAKER] Service 'itop' state changed: CLOSED -> OPEN
                        parts = msg.split("'")
                        if len(parts) >= 2:
                            service_name = parts[1]
                            if service_name in services:
                                for st_name, st_val in state_map.items():
                                    if msg.endswith(st_name):
                                        services[service_name]["state"] = st_val
                                        services[service_name]["last_change"] = time.time()
                                        break
                except Exception:
                    continue
    except Exception as e:
        print(f"Error reading log file: {e}")

    return services


def generate_prom_metrics():
    services = parse_latest_states()

    lines = [
        "# HELP dcim_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half_open)",
        "# TYPE dcim_circuit_breaker_state gauge",
    ]

    for srv, data in services.items():
        lines.append(f'dcim_circuit_breaker_state{{service="{srv}"}} {data["state"]}')

    lines.append("# HELP dcim_circuit_breaker_last_change_timestamp Timestamp of last circuit breaker state change")
    lines.append("# TYPE dcim_circuit_breaker_last_change_timestamp gauge")
    for srv, data in services.items():
        lines.append(f'dcim_circuit_breaker_last_change_timestamp{{service="{srv}"}} {data["last_change"]}')

    prom_content = "\n".join(lines) + "\n"

    try:
        # Atomic write
        tmp_file = PROM_FILE_PATH + ".tmp"
        with open(tmp_file, "w") as f:
            f.write(prom_content)
        os.rename(tmp_file, PROM_FILE_PATH)
        print(f"✓ Exported Prometheus circuit breaker metrics to {PROM_FILE_PATH}")
    except Exception as e:
        print(f"✗ Failed to write Prometheus metrics: {e}")


if __name__ == "__main__":
    generate_prom_metrics()
