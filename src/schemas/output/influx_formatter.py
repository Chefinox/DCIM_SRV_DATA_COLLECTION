import datetime

def _clean(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() in ("unknown", "none", "null") or value.upper() in ("NO_SN", "NO_IDENTIFIER"):
        return None
    return value

def _fallback_hostname(ip):
    return f"CCTV-{str(ip).replace('.', '-')}" if ip else "unknown"

def _fallback_serial(ip):
    return f"CCTV-IP-{ip.replace('.', '-')}" if ip else "NO_SN"

def format_cctv_to_influx(metrics):
    """
    Standardizes DCIM metrics into InfluxDB Line Protocol.
    Capability: Output Formatting.
    """
    measurement = "cctv_metrics"
    ip = _clean(metrics.get("ip")) or ""
    hostname = _clean(metrics.get("hostname")) or _fallback_hostname(ip)
    serial_number = _clean(metrics.get("serial_number")) or _fallback_serial(ip)
    model = _clean(metrics.get("model")) or "DS-2CD"
    
    # Tags
    tags = {
        "hostname":      hostname.replace(" ", "_"),
        "serial_number": serial_number.replace(" ", "_"),
        "ip":            ip,
        "model":         model.replace(" ", "_"),
        "manufacturer":  _clean(metrics.get("manufacturer")) or "Hikvision",
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
    if util.get("cpu") is not None: fields["cpuUtilization"] = util["cpu"]
    if util.get("memory") is not None: fields["memoryUsage"] = util["memory"]
    if util.get("memory_available") is not None: 
        fields["memoryAvailable"] = util["memory_available"]
        
    # Calculate Memory Usage Percentage
    if "memoryUsage" in fields and "memoryAvailable" in fields:
        try:
            used = float(fields["memoryUsage"])
            avail = float(fields["memoryAvailable"])
            total = used + avail
            if total > 0:
                fields["memoryUsagePct"] = (used / total) * 100
        except Exception:
            pass

    field_str = ",".join(f"{k}={v}" for k, v in fields.items())
    
    # Timestamp
    ts_ns = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1e9)
    
    return f"{measurement},{tag_str} {field_str} {ts_ns}"
