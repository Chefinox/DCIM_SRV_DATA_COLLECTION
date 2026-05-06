import datetime

def format_cctv_to_influx(metrics):
    """
    Standardizes DCIM metrics into InfluxDB Line Protocol.
    Capability: Output Formatting.
    """
    measurement = "cctv_metrics"
    
    # Tags
    tags = {
        "hostname":      metrics.get("hostname", "unknown").replace(" ", "_"),
        "serial_number": metrics.get("serial_number", "NO_SN").replace(" ", "_"),
        "ip":            metrics.get("ip", ""),
        "model":         metrics.get("model", "unknown").replace(" ", "_"),
        "device_type":   metrics.get("device_category", "cctv").lower(),
    }
    tag_str = ",".join(f"{k}={v}" for k, v in tags.items() if v)

    # Fields
    status_val = 1 if metrics.get("status") == "Online" else 0
    fields = {
        "status_online": status_val,
        "status_text":   f'"{metrics.get("status", "Offline")}"'
    }
    
    util = metrics.get("utilization", {})
    if util.get("cpu"): fields["cpuUtilization"] = util["cpu"]
    if util.get("memory"): fields["memoryUsage"] = util["memory"]

    field_str = ",".join(f"{k}={v}" for k, v in fields.items())
    
    # Timestamp
    ts_ns = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1e9)
    
    return f"{measurement},{tag_str} {field_str} {ts_ns}"
