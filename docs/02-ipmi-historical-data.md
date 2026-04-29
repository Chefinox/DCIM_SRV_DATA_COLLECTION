# Historical IPMI Metric Documentation

This document preserves the documentation for the IPMI collection method, which has been superseded by the Redfish protocol for live monitoring.

## Lenovo Servers (IPMI CSV → JSON → Elasticsearch)

### Raw Data Source
**Collector**: `ipmi_poller.py`
**Mechanism**: `ipmitool sdr list -c` executed over SSH via `sshpass`.

### Before Transformation (Raw CSV)
```csv
Ambient Temp,24,degrees C,ok,1.1,1
Fan 1 Front Tach,7790,RPM,ok,29.1,
Drive 0,A1h,ok,4.0,Drive Present
```

### After Transformation (JSON)
**Stored in**: `server-ipmi-metrics-YYYY.MM.DD`

```json
{
    "@timestamp": "2026-04-10T10:14:00.000Z",
    "category": "infrastructure",
    "device_type": "server",
    "ip": "10.50.0.11",
    "server_ipmi": {
        "Ambient_Temp_degrees_C": 24.0,
        "Fan_1_Front_Tach_RPM": 7790.0,
        "Drive_0_Status": "A1h"
    }
}
```

### Script Reference
The parsing logic was implemented in `ipmi_poller.py` using standard CSV splitting and label normalization (replacing spaces with underscores).

---
*Note: This data source is now archived. Current server monitoring uses the **Redfish** plugin in Telegraf.*
