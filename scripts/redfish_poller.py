#!/usr/bin/env python3
"""
Redfish Poller for NiFi ExecuteProcess.
Polls 5 Lenovo servers via Redfish REST API and outputs JSON-lines
matching the Telegraf 'server_redfish' measurement schema.

Endpoints polled per server:
  - /redfish/v1/Systems/1           → PowerState, Model, BIOS, SerialNumber
  - /redfish/v1/Chassis/1/Thermal   → Temperatures + Fans
  - /redfish/v1/Chassis/1/Power     → PSU + PowerControl (consumed watts)
  - /redfish/v1/Systems/1/Oem/Lenovo/Metrics/CPUSubsystemPerformance
  - /redfish/v1/Systems/1/Oem/Lenovo/Metrics/MemorySubsystemPerformance
"""
import json
import sys
import time
import urllib3

# Suppress InsecureRequestWarning for self-signed BMC certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
except ImportError:
    sys.stderr.write("ERROR: 'requests' module not found. Install with: pip3 install requests\n")
    sys.exit(1)

SERVERS = [
    {"ip": "10.50.0.2", "host": "server-HCI-01",    "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.3", "host": "server-HCI-02",    "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.4", "host": "server-HCI-03",    "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.5", "host": "server-Render-01", "user": "hndept", "pass": "F!tech@0918"},
    {"ip": "10.50.0.6", "host": "server-Render-02", "user": "root",   "pass": "F!tech@0918"},
]

TIMEOUT = 8  # seconds per HTTP request


def redfish_get(server, path):
    """GET a Redfish endpoint; returns parsed JSON or None."""
    url = f"https://{server['ip']}/redfish/v1{path}"
    try:
        resp = requests.get(
            url,
            auth=(server["user"], server["pass"]),
            verify=False,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        sys.stderr.write(f"WARN: {server['host']} {path}: {e}\n")
    return None


def poll_system(server, ts):
    """Poll /Systems/1 for power-state, model, BIOS, serial."""
    data = redfish_get(server, "/Systems/1")
    if not data:
        return
    fields = {}
    if data.get("PowerState"):
        fields["power_state"] = 1 if data["PowerState"] == "On" else 0
    tags = {
        "device_type": "server",
        "host": server["host"],
        "ip": server["ip"],
    }
    if data.get("Model"):
        tags["model"] = data["Model"]
    if data.get("BiosVersion"):
        tags["bios_version"] = data["BiosVersion"]
    if data.get("SerialNumber"):
        tags["serial_number"] = data["SerialNumber"]

    if fields:
        print(json.dumps({
            "name": "server_redfish",
            "tags": tags,
            "fields": fields,
            "timestamp": ts,
        }))


def poll_thermal(server, ts):
    """Poll /Chassis/1/Thermal for temperatures and fans."""
    data = redfish_get(server, "/Chassis/1/Thermal")
    if not data:
        return

    base_tags = {"device_type": "server", "host": server["host"], "ip": server["ip"]}

    # --- Temperatures ---
    for temp in data.get("Temperatures", []):
        name = temp.get("Name")
        reading = temp.get("ReadingCelsius")
        if name is None or reading is None:
            continue
        t = base_tags.copy()
        t["sensor"] = name
        health = (temp.get("Status") or {}).get("Health", "Unknown")
        fields = {
            "temperature_celsius": reading,
            "health_ok": 1 if health == "OK" else 0,
        }
        upper = temp.get("UpperThresholdCritical")
        if upper is not None:
            fields["upper_threshold_critical"] = upper

        print(json.dumps({
            "name": "server_redfish_thermal",
            "tags": t,
            "fields": fields,
            "timestamp": ts,
        }))

    # --- Fans ---
    for fan in data.get("Fans", []):
        name = fan.get("Name")
        reading = fan.get("Reading")
        if name is None or reading is None:
            continue
        t = base_tags.copy()
        t["fan"] = name
        health = (fan.get("Status") or {}).get("Health", "Unknown")
        fields = {
            "fan_speed_rpm": reading,
            "health_ok": 1 if health == "OK" else 0,
        }
        print(json.dumps({
            "name": "server_redfish_fan",
            "tags": t,
            "fields": fields,
            "timestamp": ts,
        }))


def poll_power(server, ts):
    """Poll /Chassis/1/Power for PSU and total power consumed."""
    data = redfish_get(server, "/Chassis/1/Power")
    if not data:
        return

    base_tags = {"device_type": "server", "host": server["host"], "ip": server["ip"]}

    # --- Power Supplies ---
    for psu in data.get("PowerSupplies", []):
        name = psu.get("Name")
        if name is None:
            continue
        t = base_tags.copy()
        t["psu"] = name
        health = (psu.get("Status") or {}).get("Health", "Unknown")
        fields = {"health_ok": 1 if health == "OK" else 0}
        output = psu.get("LastPowerOutputWatts")
        if output is not None:
            fields["output_watts"] = output
        capacity = psu.get("PowerCapacityWatts")
        if capacity is not None:
            fields["capacity_watts"] = capacity
        line_v = psu.get("LineInputVoltage")
        if line_v is not None:
            fields["line_input_voltage"] = line_v

        print(json.dumps({
            "name": "server_redfish_psu",
            "tags": t,
            "fields": fields,
            "timestamp": ts,
        }))

    # --- Power Control (total server power) ---
    for pc in data.get("PowerControl", []):
        name = pc.get("Name", "unknown")
        consumed = pc.get("PowerConsumedWatts")
        if consumed is None:
            continue
        t = base_tags.copy()
        t["power_control"] = name
        fields = {"power_consumed_watts": consumed}
        cap = pc.get("PowerCapacityWatts")
        if cap is not None:
            fields["power_capacity_watts"] = cap
        avg = (pc.get("PowerMetrics") or {}).get("AverageConsumedWatts")
        if avg is not None:
            fields["average_consumed_watts"] = avg
        max_w = (pc.get("PowerMetrics") or {}).get("MaxConsumedWatts")
        if max_w is not None:
            fields["max_consumed_watts"] = max_w
        min_w = (pc.get("PowerMetrics") or {}).get("MinConsumedWatts")
        if min_w is not None:
            fields["min_consumed_watts"] = min_w

        print(json.dumps({
            "name": "server_redfish_power",
            "tags": t,
            "fields": fields,
            "timestamp": ts,
        }))


def poll_oem_utilization(server, ts):
    """Poll Lenovo OEM CPU/Memory utilization metrics."""
    base_tags = {"device_type": "server", "host": server["host"], "ip": server["ip"]}
    fields = {}

    for metric, field_name in [
        ("CPUSubsystemPerformance", "cpu_utilization"),
        ("MemorySubsystemPerformance", "memory_usage"),
    ]:
        data = redfish_get(server, f"/Systems/1/Oem/Lenovo/Metrics/{metric}")
        if data:
            container = data.get("Container", [])
            if container and len(container) > 0:
                val = container[0].get("MetricValue")
                if val is not None:
                    fields[field_name] = val

    if fields:
        print(json.dumps({
            "name": "server_redfish_util",
            "tags": base_tags,
            "fields": fields,
            "timestamp": ts,
        }))


def main():
    ts = int(time.time())
    for server in SERVERS:
        try:
            poll_system(server, ts)
            poll_thermal(server, ts)
            poll_power(server, ts)
            poll_oem_utilization(server, ts)
        except Exception as e:
            sys.stderr.write(f"ERROR polling {server['host']}: {e}\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
