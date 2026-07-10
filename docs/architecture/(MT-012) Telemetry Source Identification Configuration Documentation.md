# (MT-012) Telemetry Source Identification Configuration Documentation

# 1. System Configuration Overview

Dokumen ini menjelaskan konfigurasi teknis seluruh sumber data telemetri yang masuk ke pipeline DCIM v4.4. Setiap poller, konfigurasi SNMP/Redfish/ISAPI, dan scheduling NiFi/systemd didokumentasikan secara lengkap.

Arsitektur koleksi:

```
Physical Device (L1)
        ↓ (Redfish / SNMP / ISAPI)
Poller Script (Python)
        ↓ (JSON stdout)
NiFi ExecuteProcess / Systemd Daemon
        ↓ (Kafka Producer)
Kafka Raw Topic (dcim.raw.*)
```

***

# 2. Server Redfish Configuration

## Poller Script — Telemetry

File: `scripts/redfish_poller.py`

```python
SERVERS = [
    {"ip": "10.50.0.2", "host": "server-HCI-01",    "user": "hndept", "pass": REDFISH_PASS},
    {"ip": "10.50.0.3", "host": "server-HCI-02",    "user": "hndept", "pass": REDFISH_PASS},
    {"ip": "10.50.0.4", "host": "server-HCI-03",    "user": "hndept", "pass": REDFISH_PASS},
    {"ip": "10.50.0.5", "host": "server-Render-01", "user": "hndept", "pass": REDFISH_PASS},
    {"ip": "10.50.0.6", "host": "server-Render-02", "user": "root",   "pass": REDFISH_PASS}
]

TIMEOUT = 8  # seconds per HTTP request
```

Credential menggunakan Vault via `src/utils/secrets.py`:

```python
from src.utils.secrets import get_secret
REDFISH_PASS = get_secret("redfish_pass", "REDFISH_PASS")
```

Redfish endpoints per server:

```
/redfish/v1/Systems/1                          → PowerState, Model, BIOS, SerialNumber
/redfish/v1/Chassis/1/Thermal                  → Temperatures + Fans
/redfish/v1/Chassis/1/Power                    → PSU + PowerControl (consumed watts)
/redfish/v1/Systems/1/Oem/Lenovo/Metrics/CPUSubsystemPerformance    → CPU util (OEM)
/redfish/v1/Systems/1/Oem/Lenovo/Metrics/MemorySubsystemPerformance → Mem util (OEM)
```

## Poller Script — CPU/Memory Utilization

File: `scripts/redfish_telemetry_poller.py`

Skrip terpisah yang fokus pada Lenovo XCC OEM endpoint untuk utilisasi CPU dan memori. Output InfluxDB Line Protocol:

```
server_redfish_util,hostname=server-HCI-01 cpu_utilization=12.5,memory_usage=67.3
```

## Poller Script — Server Inventory (Daily)

File: `scripts/server_inventory_collector.py`

```python
REDFISH_SERVERS = [
    {"ip": "10.50.0.2", "hostname": "SERVER-HCI-01"},
    {"ip": "10.50.0.3", "hostname": "SERVER-HCI-02"},
    {"ip": "10.50.0.4", "hostname": "SERVER-HCI-03"},
    {"ip": "10.50.0.5", "hostname": "SERVER-RENDER-01"},
    {"ip": "10.50.0.6", "hostname": "SERVER-RENDER-02"}
]
REDFISH_USER = "hndept"
```

Jadwal: Daily 01:00 WIB via NiFi ExecuteProcess.

Output topic: `dcim.raw.hardware.server.inventory`

***

# 3. UPS SNMP Configuration

## Poller Script

File: `scripts/snmp_ups_poller.py`

```python
UPS_IP = "192.168.100.140"
SNMP_USER = "hndept"
AUTH_PASS = "F!tech0918"
PRIV_PASS = "F!tech0918"
```

SNMP version: v3 (authPriv, SHA + AES)

Tool: `snmpwalk` CLI

## OID List (30+ OIDs)

```python
OIDS = {
    "system_name": ".1.3.6.1.2.1.1.5.0",
    "system_location": ".1.3.6.1.2.1.1.6.0",
    "model": ".1.3.6.1.4.1.935.1.1.1.1.1.1.0",
    "status": ".1.3.6.1.4.1.935.1.1.1.4.1.1.0",
    "battery_capacity": ".1.3.6.1.4.1.935.1.1.1.2.2.1.0",
    "battery_runtime_remain": ".1.3.6.1.4.1.935.1.1.1.2.2.3.0",
    "battery_temp": ".1.3.6.1.4.1.935.1.1.1.2.2.2.0",
    "input_voltage": ".1.3.6.1.4.1.935.1.1.1.3.2.1.0",
    "output_voltage": ".1.3.6.1.4.1.935.1.1.1.4.2.1.0",
    "output_load": ".1.3.6.1.4.1.935.1.1.1.4.2.3.0",
    "serial_number": ".1.3.6.1.2.1.33.1.1.1.0",
    "firmware": ".1.3.6.1.2.1.33.1.1.3.0",
    "input_frequency_L1": ".1.3.6.1.2.1.33.1.3.3.1.2.1",
    "input_voltage_L1": ".1.3.6.1.2.1.33.1.3.3.1.3.1",
    "input_voltage_L2": ".1.3.6.1.2.1.33.1.3.3.1.3.2",
    "input_voltage_L3": ".1.3.6.1.2.1.33.1.3.3.1.3.3",
    "output_voltage_L1": ".1.3.6.1.2.1.33.1.4.4.1.2.1",
    "output_voltage_L2": ".1.3.6.1.2.1.33.1.4.4.1.2.2",
    "output_voltage_L3": ".1.3.6.1.2.1.33.1.4.4.1.2.3",
    "output_current_L1": ".1.3.6.1.2.1.33.1.4.4.1.3.1",
    "output_current_L2": ".1.3.6.1.2.1.33.1.4.4.1.3.2",
    "output_current_L3": ".1.3.6.1.2.1.33.1.4.4.1.3.3",
    "output_load_L1": ".1.3.6.1.2.1.33.1.4.4.1.5.1",
    "output_load_L2": ".1.3.6.1.2.1.33.1.4.4.1.5.2",
    "output_load_L3": ".1.3.6.1.2.1.33.1.4.4.1.5.3"
}
```

Output topic: `dcim.raw.power.ups`

***

# 4. NAS SNMP Configuration

## Poller Script

File: `scripts/nas_poller.py`

```python
IPS = [
    "10.50.0.105", "10.50.0.106", "10.50.0.107",
    "10.50.0.108", "10.50.0.109", "10.50.0.110"
]
```

SNMP version: v3 (authNoPriv, SHA)

```bash
snmpwalk -Oqn -v3 -l authNoPriv -u hndept -a SHA -A F!tech0918 -t 2 -r 1 <IP> <OID>
```

## OID Categories

| OID Root | Kategori | Data |
|----------|----------|------|
| `.1.3.6.1.2.1.1.5.0` | System | hostname |
| `.1.3.6.1.4.1.6574.1.5.1.0` | Synology | model |
| `.1.3.6.1.4.1.6574.1.5.2.0` | Synology | serial_number |
| `.1.3.6.1.4.1.6574.2.1.1.*` | Synology Disk | disk ID, model, type, temp, status |
| `.1.3.6.1.4.1.6574.3.1.1.*` | Synology RAID | RAID name, status |
| `.1.3.6.1.2.1.25.2.3.1.*` | Host Resources | storage usage (memory, volume) |
| `.1.3.6.1.2.1.31.1.1.1.*` | IF-MIB | network rx/tx bytes |

Output topic: `dcim.raw.storage.nas`

***

# 5. Network SNMP Configuration

## Poller Script

File: `scripts/mikrotik_poller.py`

```python
IPS = ["172.16.35.1", "172.16.35.2", "172.16.35.3", "172.16.35.5", "172.16.35.6"]
```

SNMP version: v2c, community: `public`

```bash
snmpwalk -Oqn -v2c -c public -t 2 -r 1 <IP> <OID_PREFIX>
```

## OID Categories

```python
OIDS = [
    ".1.3.6.1.2.1.1",           # System (sysName, sysDescr, uptime)
    ".1.3.6.1.2.1.2.2",         # Interfaces status
    ".1.3.6.1.2.1.31.1.1",      # Interfaces stats (ifXTable)
    ".1.3.6.1.2.1.25.2",        # Storage/HR
    ".1.3.6.1.4.1.14988.1.1.1", # MikroTik specific (CPU, temp)
]
```

Output topics: `dcim.raw.network.snmp` + `dcim.raw.network.interfaces`

***

# 6. CCTV & NVR ISAPI Configuration

## Daemon Poller

File: `scripts/hikvision_poller_daemon.py`

```python
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
    "192.168.1.33"  # Total: 31 units (skip .32)
]
```

## Systemd Service

File: `configs/systemd/dcim-cctv-poller.service`

```ini
[Unit]
Description=DCIM CCTV/NVR Poller Daemon
After=network.target

[Service]
Type=simple
User=infra
ExecStart=/usr/bin/python3 /home/infra/dcim_metrics_project/scripts/hikvision_poller_daemon.py
Restart=always
RestartSec=30
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
```

Output topic: `dcim.raw.device.isapi`

***

# 7. NiFi ExecuteProcess Configuration

Apache NiFi 1.24.0 berjalan di Docker (`nifi/docker-compose.yml`) dengan `network_mode: host`.

Semua poller (kecuali CCTV daemon) dijadwalkan via NiFi processor group "Collection":

| Processor | Script | Scheduling | Interval |
|-----------|--------|-----------|----------|
| ExecuteProcess (Server Redfish) | `redfish_poller.py` | Timer driven | 60s |
| ExecuteProcess (Server CPU/Mem) | `redfish_telemetry_poller.py` | Timer driven | 30s |
| ExecuteProcess (Server Inventory) | `server_inventory_collector.py` | Cron driven | `0 1 * * *` |
| ExecuteProcess (UPS SNMP) | `snmp_ups_poller.py` | Timer driven | 60s |
| ExecuteProcess (NAS SNMP) | `nas_poller.py` | Timer driven | 120s |
| ExecuteProcess (Network SNMP) | `mikrotik_poller.py` | Timer driven | 60s |

Scripts mounted ke NiFi via Docker volume:

```yaml
volumes:
  - /home/infra/dcim_metrics_project/scripts:/opt/nifi/nifi-current/scripts:ro
```

***

# 8. Credential Management

Semua credential dikelola melalui **HashiCorp Vault 1.15** (`vault/docker-compose.yml`):

| Secret Path | Digunakan Oleh |
|-------------|---------------|
| `secret/dcim/redfish_pass` | Redfish pollers (server) |
| `secret/dcim/postgres` | Lineage tracker, SQL consumer |
| `secret/dcim/ralph` | Ralph sync |

Fallback chain (dari `src/utils/secrets.py`):

```
Vault AppRole → Docker Secret (/run/secrets/dcim/*) → Environment Variable
```

Docker secrets juga dikonfigurasi di `nifi/docker-compose.yml`:

```yaml
secrets:
  redfish_pass:
    file: /run/secrets/dcim/redfish_pass
  ups_snmp_auth_pass:
    file: /run/secrets/dcim/ups_snmp_auth_pass
  ups_snmp_priv_pass:
    file: /run/secrets/dcim/ups_snmp_priv_pass
  nas_pass_snmp:
    file: /run/secrets/dcim/nas_pass_snmp
  hikvision_nvr_pass:
    file: /run/secrets/dcim/hikvision_nvr_pass
  hikvision_cam_pass:
    file: /run/secrets/dcim/hikvision_cam_pass
```

***

# 9. Operational Commands

## Menjalankan Poller Manual

```bash
# Server Redfish telemetry
python3 /home/infra/dcim_metrics_project/scripts/redfish_poller.py

# Server CPU/Memory utilization
python3 /home/infra/dcim_metrics_project/scripts/redfish_telemetry_poller.py

# Server inventory deep scan
python3 /home/infra/dcim_metrics_project/scripts/server_inventory_collector.py

# UPS SNMP
python3 /home/infra/dcim_metrics_project/scripts/snmp_ups_poller.py

# NAS SNMP
python3 /home/infra/dcim_metrics_project/scripts/nas_poller.py

# Network SNMP
python3 /home/infra/dcim_metrics_project/scripts/mikrotik_poller.py

# CCTV daemon (foreground test)
python3 /home/infra/dcim_metrics_project/scripts/hikvision_poller_daemon.py
```

## Service Management

```bash
# Restart CCTV daemon
sudo systemctl restart dcim-cctv-poller.service

# Check NiFi status
docker ps --filter name=dcim-nifi

# NiFi Web UI
# https://10.70.0.56:8443/nifi
```

***

# 10. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial configuration documentation |
