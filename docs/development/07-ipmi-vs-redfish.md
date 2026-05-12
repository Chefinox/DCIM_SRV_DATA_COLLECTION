# Protocol Comparison: IPMI vs Redfish

Through the implementation of the DCIM Metrics collection, we have tested and deployed both Redfish (via Telegraf) and IPMI (via local Python Poller) for hardware metric aggregation. 

This document outlines the comparative strengths and weaknesses of both protocols for this environment.

---

## 1. High-Level Overview

| Feature | IPMI (Intelligent Platform Mgmt Interface) | Redfish (DMTF Standard) |
|---|---|---|
| **Age** | Legacy (Released 1998) | Modern (Released 2015) |
| **Transport Protocol** | RMCP/UDP or Local System Bus (`/dev/ipmi0`) | HTTP/HTTPS (REST API) |
| **Data Format** | Binary / CSV (via `ipmitool`) | Highly Structured JSON |
| **Security** | Basic Cipher Suites, often disabled over LAN by vendors | TLS/SSL with strong Modern Ciphers |
| **Human Readable** | Poor (Requires parsing tools like `ipmitool`) | Excellent (Browser-friendly) |
| **Data Scope** | Fixed low-level hardware sensors (Temperatures, Fans) | Expandable schemas covering logs, drives, network speeds |

---

## 2. In-Depth Comparison of Current Environment

### A. Data Accessibility

**IPMI Configuration:**
In our environment, the Lenovo Baseboard Management Controllers (BMC) default to blocking IPMI over LAN requests for security. To successfully poll IPMI data, we bypass the network and utilize SSH (`ipmi_poller.py`) to query the physical PCIe-to-BMC bus on the Proxmox host.
* **Pro**: Bypasses network segmentation or blocked UDP ports entirely.
* **Con**: Requires root password access to the hypervisor OS, rather than purely interacting with the management board.

**Redfish Configuration:**
The Redfish API runs completely independent of the installed OS natively on the BMC module. We query it directly over IPv4 `https://10.50.0.5` utilizing standard Telegraf REST plugins (`inputs.redfish`).
* **Pro**: Zero touch needed on the Proxmox OS. Clean agentless approach relying only on BMC credentials.
* **Con**: Requires L3 network routing to the BMC management subnet.

### B. Payload Structure & Density

**IPMI Output (`ipmitool sdr list`)**
IPMI returns static hardware registers. It provides an immediate and immense wall of highly granular, low-level data points (249 specific registers on our Lenovo nodes).
* **Strength**: Exhaustive sensor coverage. (e.g., specific motherboard VRM faults, individual DIMM PMIC temperatures).
* **Weakness**: Status codes are typically opaque HEX values (e.g., `Drive_7_Status`: `"A8h"`). The JSON output requires us to forcefully manipulate the CSV headers to prevent Elasticsearch ingestion errors.

**Redfish Output (`HTTP GET /redfish/v1/Chassis/1/Thermal`)**
Redfish returns a hierarchical taxonomy of system properties, modeled dynamically for the installed hardware.
* **Strength**: Human-readable contextual status (e.g., `Status.Health`: `"OK"`). Includes upper and lower critical thresholds seamlessly alongside the current reading. 
* **Weakness**: Takes multiple API loops/calls to drill down and collect data across all branches (Thermal tree, Power tree, Network tree) compared to a single `ipmitool sdr` blast.

---

## 3. Storage and Scaling in Elasticsearch

### Elasticsearch Ingestion

**Using IPMI Data:**
When `ipmitool` metrics hit Elasticsearch, they are unstructured fields on a massive flat document. An index containing IPMI metrics will have hundreds of fields (`DIMM_1_Temp_degrees_C`, `DIMM_2_Temp_degrees_C`, etc.). This causes "Mapping Explosions" in Kibana as thousands of sparse metrics are generated and indexed separately. 

**Using Redfish Data:**
Telegraf's `inputs.redfish` plugin natively unrolls arrays. Each fan or temperature sensor gets submitted to Elasticsearch as a separate row grouped by common labels, e.g.:
```json
{
   "measurement_name": "redfish_thermal_fans",
   "FanName": "Fan 1 Front Tach",
   "Reading": 7790
}
```
This relational structure is drastically easier to aggregate or average using Kibana visualizations.

---

## 4. Final Verdict & Recommendation

While the **IPMI** poller we have built is an excellent fallback—and definitively retrieves an incredible amount of raw sensor diagnostics through OS tunneling—it should remain a secondary mechanism.

**Recommendation:** Base all core infrastructure dashboards on **Redfish** data.
* Redfish's native JSON payloads are purpose-built for the ELK stack.
* Redfish provides human-readable context warnings (`Warning`, `Critical`) natively.
* Polling directly over the BMC network provides a standard "out-of-band" management tier, keeping OS security isolation intact.
