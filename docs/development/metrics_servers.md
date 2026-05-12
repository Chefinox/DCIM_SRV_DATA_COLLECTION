# Metric Documentation: Servers (Lenovo Redfish)

**Sources**: 10.50.0.2 - 10.50.0.6
**Collector**: Telegraf Redfish Input

| Metric Category | Fields Collected | Description |
|---|---|---|
| **Health** | `health_status` | Overall system health (OK, Warning, Critical) |
| **Power** | `power_consumed_watts` | Total power consumption in Watts |
| **Temperature** | `temp_celsius` | Temperatures for CPU, PCH, and Exhaust |
| **Fans** | `fan_speed_rpm` | Rotational speed of all system fans |
| **Processor** | `cpu_health`, `cpu_status` | Status of individual CPU sockets |
| **Memory** | `mem_health`, `mem_status` | Status of DIMM slots |
| **Storage** | `drive_health` | Status of physical drives/arrays |

**Tags**:
- `host`: server-HCI-01, server-HCI-02, ..., server-Render-02
- `source`: IP Address of the BMC
