# Common Metrics Across All Categories

These metrics are present in all collected data types (UPS, Servers, CCTV, Mikrotik) for unified dashboarding.

| Common Field | Unified Name in ES | Description |
|---|---|---|
| **Timestamp** | `@timestamp` | Time of collection (ISO8601) |
| **Device Name** | `host` or `device` | The human-readable name of the hardware |
| **IP Address** | `ip` or `agent_host` | The network address of the device |
| **Status** | `status` | Boolean or Keyword indicating Up/Down or OK/Critical |
| **Vendor** | `vendor` or `model` | Manufacturer information (APC, Lenovo, Hikvision, Mikrotik) |

**Recommendation for Unified Dashboarding**:
Create an **Index Pattern** in Kibana that covers all indices:
`telegraf-metrics-*, cctv-metrics-*, server-ipmi-* (or redfish)`
This allows you to create a "Global Health" table.
