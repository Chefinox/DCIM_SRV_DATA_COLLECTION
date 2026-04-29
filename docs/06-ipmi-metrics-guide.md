# IPMI Data Collection Guide

This document covers how we utilize IPMI (Intelligent Platform Management Interface) to monitor the physical Lenovo servers via their underlying Proxmox hypervisor hosts.

---

## 1. How We Collect IPMI Data

Because the Lenovo Baseboard Management Controllers (BMC / XCC) at `10.50.0.x` restrict remote IPMI-over-LAN (RMCP+) traffic, we collect IPMI data locally by tunneling through the host OS.

### Collection Architecture
1. **Python Script (`ipmi_poller.py`)**: Runs on the collection server every minute via Cron.
2. **SSH Tunneling**: Uses `sshpass` to log into the Proxmox host (e.g. `10.50.0.11`) as `root`.
3. **Local Bus Query**: Executes `ipmitool sdr list -c` on the Proxmox host. This commands the host kernel to query the BMC firmware directly across the internal PCI/I2C system bus (`/dev/ipmi0`), completely bypassing network firewalls.
4. **Parsing**: The python script catches the raw CSV output, removes invalid readings, renames variables to be JSON-safe, and packages them with device tags.
5. **Elasticsearch Ingest**: The payload is pushed directly to the `server-ipmi-metrics-YYYY.MM.DD` index via HTTP POST.

---

## 2. All Available IPMI Metrics

A single `ipmitool sdr list` query against the Lenovo ThinkSystem returns ~250 discrete sensors. Below are the primary categorized metrics we extract: 

### Thermal Metrics
| Metric Field | Unit | Description |
|---|---|---|
| `Ambient_Temp_degrees_C` | °C | Fresh air temperature entering chassis |
| `Exhaust_Temp_degrees_C` | °C | Heated air temperature leaving chassis |
| `CPU_1_Temp_degrees_C` | °C | Package temperature for processor socket 1 |
| `CPU_2_Temp_degrees_C` | °C | Package temperature for processor socket 2 |
| `DIMM_X_Temp_degrees_C` | °C | Memory module temperature (Slots 1-24) |
| `PCIe_X_OverTemp_Status` | String | Over-temperature alarm for PCIe Risers/Slots |

### Cooling / Fan Metrics
| Metric Field | Unit | Description |
|---|---|---|
| `Fan_X_Front_Tach_RPM` | RPM | Speed of front cooling fans |
| `Fan_X_Rear_Tach_RPM` | RPM | Speed of rear chassis cooling fans |
| `Fan_Mismatch_Status` | String | Alert if asymmetric fans are installed |

### Power Metrics
| Metric Field | Unit | Description |
|---|---|---|
| `Sys_Power_Watts` | Watts | Total chassis power consumption |
| `CPU_Power_Watts` | Watts | Power consumption dedicated to CPUs |
| `Mem_Power_Watts` | Watts | Power consumption dedicated to RAM |
| `PSU_X_AC_In_Pwr_Watts` | Watts | Input power draw for Power Supply X |
| `PSU_X_DC_Out_Pwr_Watts` | Watts | Output power supplied by Power Supply X |

### Voltage & Resource Health
| Metric Field | Unit | Description |
|---|---|---|
| `SysBrd_12V_Volts` | Volts | 12V rail voltage on motherboard |
| `SysBrd_5V_Volts`| Volts | 5V rail voltage on motherboard |
| `CMOS_Battery_Volts`| Volts | CMOS battery retention voltage |
| `CPU_Utilization_percent`| % | Aggregate CPU load estimate |
| `Drive_X_Status` | String | Status code for local SATA/SAS drives |

---

## 3. Raw Data Before Elasticsearch

When `ipmitool sdr list -c` executes locally on the Proxmox host, the raw string output returned over the SSH tunnel is in raw CSV (Comma Separated Values) format:

```csv
Ambient Temp,24,degrees C,ok,1.1,1
Exhaust Temp,28,degrees C,ok,1.2,
CPU 1 Temp,45,degrees C,ok,3.1,
DIMM 1 Temp,no reading,degrees C,ns,7.1,
Fan 1 Front Tach,7790,RPM,ok,29.1,
Sys Power,264,Watts,ok,21.1,
Drive 0,A1h,ok,4.0,Drive Present
```
*Note missing readings output `no reading` and must be dropped by the poller.*

---

## 4. The Data After Reaching Elasticsearch

The Python script sanitizes the CSV field names, drops empty sensors, flattens the types, and structures it into a flat JSON payload. This is exactly what ends up stored as a single document in Elasticsearch under `server-ipmi-metrics-*`:

```json
{
  "@timestamp": "2026-04-10T10:14:00.672589+00:00",
  "measurement_name": "server_ipmi",
  "tag": {
    "host": "server-Render-01",
    "proxmox_node": "10.50.0.11"
  },
  "server_ipmi": {
    "Ambient_Temp_degrees_C": 24.0,
    "Exhaust_Temp_degrees_C": 28.0,
    "CPU_1_Temp_degrees_C": 45.0,
    "Fan_1_Front_Tach_RPM": 7790.0,
    "Sys_Power_Watts": 264.0,
    "Drive_0_Status": "A1h"
  }
}
```
This flattened format makes it immediate and simple to build Kibana dashboards with queries like `server_ipmi.Sys_Power_Watts > 250`.
