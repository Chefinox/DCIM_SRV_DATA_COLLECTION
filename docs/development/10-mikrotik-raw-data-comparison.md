# MikroTik Raw Data Comparison — Multi-Model Analysis

This document analyzes the architectural differences in raw SNMP data across the various MikroTik models in our infrastructure.

## 📡 Model Overview
We performed a full, unfiltered SNMP walk on each unique hardware model. The raw logs are stored in the `/docs` folder.

| Model | Management IP | RAM (Reported) | CPU Freq | Walk File Size |
| :--- | :--- | :--- | :--- | :--- |
| **CCR2004-16G-2S+** | `172.16.35.1` | 4 GB | 1700 MHz | 685 KB |
| **CRS326-24S+2Q+** | `172.16.35.2` | 128 MB | 650 MHz | 460 KB |
| **CRS354-48G-4S+2Q+** | `172.16.35.3` | 128 MB | 650 MHz | 648 KB |
| **CRS312-4C+8XG** | `172.16.35.6` | 128 MB | 650 MHz | 185 KB |

---

## 🏗️ Feature Support Matrix
This table confirms which hardware families support specific metric groups based on our SNMP probes.

| Feature Group | CCR2004 | CRS326 | CRS354 | CRS312 |
| :--- | :---: | :---: | :---: | :---: |
| **System Info** (Name/Uptime/Loc) | ✅ | ✅ | ✅ | ✅ |
| **CPU Core Load** (Per-Core) | ✅ | ✅ | ✅ | ✅ |
| **Bridge/VLAN Stats** | ✅ | ✅ | ✅ | ✅ |
| **High-Precision If Counters** | ✅ | ✅ | ✅ | ✅ |
| **Multicast/Unicast Packet Stats** | ✅ | ✅ | ✅ | ✅ |
| **Interface Last Change** | ✅ | ✅ | ✅ | ✅ |
| **Inbound/Outbound Discards** | ✅ | ✅ | ✅ | ✅ |
| **PSU Redundancy Status** | ✅ | ⬜ | ✅ | ⬜ |
| **Wireless Metrics** (MIB Level) | ✅ | ✅ | ✅ | ✅ |

> **Note:** While the Wireless MIB tree is present on all models (✅), those without physical WiFi radios will report `0` for client count and rates.

---

## 🔍 Key Structural Differences

### 1. Object Density (Log Size)
*   **CCR2004 (Cloud Core Router):** Returns nearly **700KB** of data. This is due to a significantly larger number of internal routing objects, queues, and hardware sensors compared to the switch (CRS) line.
*   **CRS312 (Switch):** Returns the least amount of data (**185KB**). This model is highly specialized for 10G/Copper switching and has a much simpler SNMP tree.
*   **CRS354 (48-port Switch):** Returns **648KB**. While it is a switch, the sheer number of physical interfaces (48 ports) causes the `ifTable` and `ifXTable` to explode in size.

### 2. Physical Sensor Availability
Based on the raw walks, only the **CCR2004** and **CRS354** consistently expose individual PSU (Power Supply) health status via the MikroTik Private MIB.
*   **CCR2004 Sensors:** Exposes `cpu-temperature`, `voltage`, `current`, and `psu-state`.
*   **CRS312 Sensors:** Only exposes basic system metrics; lacks detailed voltage/current monitoring in the standard walk.

### 3. CPU & Memory Discrepancies
*   **Memory Index:** All models use the same index for memory in the Host Resources MIB (`.1.3.6.1.2.1.25.2.3.1.3.65536`).
*   **RAM Reporting:** Interestingly, the **CRS354** (which has 512MB RAM) reports only **128MB** to the standard SNMP host resources table. This suggests the switch OS reserves a large portion of RAM for the switching buffer that is hidden from standard SNMP monitoring.
*   **CPU:** The **CCR2004** is significantly more powerful (1.7GHz) than the switch line (650MHz), reflecting its role as the core router handling heavy traffic.

---

## 📂 Raw Files Location
The full, unfiltered data for each model can be found at:
*   [raw_mikrotik_CCR2004.txt](file:///home/infra/dcim_metrics_project/docs/raw_mikrotik_CCR2004.txt)
*   [raw_mikrotik_CRS312.txt](file:///home/infra/dcim_metrics_project/docs/raw_mikrotik_CRS312.txt)
*   [raw_mikrotik_CRS326.txt](file:///home/infra/dcim_metrics_project/docs/raw_mikrotik_CRS326.txt)
*   [raw_mikrotik_CRS354.txt](file:///home/infra/dcim_metrics_project/docs/raw_mikrotik_CRS354.txt)

---

## 📊 Standardized Metrics Set (All Models)
The following metrics are now standardized across all MikroTik models and available in Elasticsearch.

| Type | Metric Name | Source OID / Method |
| :--- | :--- | :--- |
| **System** | `system_name` | `.1.3.6.1.2.1.1.5.0` |
| **System** | `system_uptime` | `.1.3.6.1.2.1.1.3.0` |
| **System** | `system_location` | `.1.3.6.1.2.1.1.6.0` |
| **System** | `system_contact` | `.1.3.6.1.2.1.1.4.0` |
| **System** | `system_description` | `.1.3.6.1.2.1.1.1.0` |
| **System** | `system_object_id` | `.1.3.6.1.2.1.1.2.0` |
| **Hardware** | `cpu_load` | MikroTik Private MIB (`.1.3.6.1.4.1.2021.11.10.0`) |
| **Hardware** | `cpu_frequency` | MikroTik Private MIB (`.1.3.6.1.4.1.14988.1.1.3.14.0`) |
| **Hardware** | `cpu_count` | MikroTik Private MIB (`.1.3.6.1.4.1.14988.1.1.3.8.0`) |
| **Memory** | `memory_total_kb` | Host Resources (`.1.3.6.1.2.1.25.2.3.1.5.65536`) |
| **Memory** | `memory_used_kb` | Host Resources (`.1.3.6.1.2.1.25.2.3.1.6.65536`) |
| **Memory** | `memory_free_kb` | MikroTik Private (`.1.3.6.1.4.1.14988.1.1.3.11.0`) |
| **Storage** | `disk_used_kb` | Host Resources (`.1.3.6.1.2.1.25.2.3.1.6.131072`) |
| **Storage** | `hdd_size_kb` | Host Resources (`.1.3.6.1.2.1.25.2.3.1.5.131072`) |

### Advanced Interface Stats (`net_interface`)
| Field Name | Description |
| :--- | :--- |
| `if_name` | Physical port name |
| `if_speed` | Link speed (bps) |
| `if_oper_status` | Current state (`1`=Up, `2`=Down) |
| `if_in_octets` | Total Bytes In |
| `if_out_octets` | Total Bytes Out |
| `if_in_errors` | Rx Errors |
| `if_out_errors` | Tx Errors |
| `if_in_discards` | Rx Discards (Queue Overflow) |
| `if_out_discards`| Tx Discards (Queue Overflow) |
| `if_admin_status`| Configured Port State (`1`=Up, `2`=Down) |
| `if_oper_status` | Physical Link State (`1`=Up, `2`=Down) |
| `if_in_ucast_pkts`| Unicast Packets In |
| `if_out_ucast_pkts`| Unicast Packets Out |
| `if_in_mcast_pkts`| Multicast Packets In |
| `if_out_mcast_pkts`| Multicast Packets Out |
| `if_last_change` | Timestamp of last link event |

### Wireless (AP Models Only)
*   `wifi_clients_count`, `wifi_frequency`, `wifi_tx_power`, `wifi_noise_floor`, `wifi_overall_tx_rate`, `wifi_overall_rx_rate`
