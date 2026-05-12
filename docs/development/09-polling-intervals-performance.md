# Polling Intervals and Performance Analysis

This document details the optimized collection intervals for infrastructure devices and the performance testing results used to determine them.

## 🏁 Summary of Configuration
| Device Category | Target IPs | Protocol | New Interval | Samples per Hour |
| :--- | :--- | :--- | :--- | :--- |
| **APC UPS** | `192.168.100.140` | SNMPv3 | **10 Seconds** | 360 |
| **Servers** | `10.50.0.2 - 0.6` | Redfish | **20 Seconds** | 180 |
| **MikroTik** | `172.16.35.x` | SNMPv2c | **10 Seconds** | 360 |
| **CCTV** | `192.168.1.x` | ISAPI (Python) | 60 Seconds | 60 |

---

## ⚡ Performance Testing Results (2026-04-14)
The intervals for Redfish servers were determined by measuring the actual response time for a full thermal sensor scan across the cluster.

### Redfish "Race" Results
Testing the time to complete a `/redfish/v1/Chassis/1/Thermal` request:

| Server IP | Response Time | Load Impact |
| :--- | :--- | :--- |
| **10.50.0.2** | 2.004s | Low |
| **10.50.0.3** | 1.355s | Low |
| **10.50.0.4** | 1.567s | Low |
| **10.50.0.5** | 0.967s | Minimal |
| **10.50.0.6** | 1.930s | Low |

**Total Cluster Collection Time:** ~7.82 Seconds

### 🧠 Rationale for 20s Interval
While 10s was technically possible (total time 7.8s < 10s), it left only ~2 seconds of buffer. Any network jitter or high management chip load would cause a **Backlog** (where a new request starts before the previous one finishes). 
*   **Selected Buffer:** 12.18 Seconds (Safety margin of 150%).
*   **Reliability:** High. Guaranteed to complete even if one server slows down significantly.

---

## 🛡️ Monitoring the Backlog
To ensure these intervals remain safe, check the Telegraf logs for "collection took longer than its interval" errors:

```bash
sudo journalctl -u telegraf --since "1 hour ago" | grep "longer than its interval"
```

If these errors appear regularly, the interval should be increased to preserve hardware stability.
