# Historical Redfish Configuration (Deprecated in favor of IPMI)

This document archives the previous Redfish-based metric collection strategy for Lenovo servers, for historical or comparison purposes. We currently use an IPMI approach to gather data natively.

---

## 1. Raw Device Data (Redfish)

## 2. Lenovo Servers — Redfish API Raw Response

**Queried by:** Telegraf `inputs.redfish`
**Endpoint:** `https://10.50.0.2/redfish/v1/Chassis/1/Thermal`
**Protocol:** HTTPS REST, Basic Auth

The Redfish API returns a large JSON object. Below is a representative subset from the Thermal endpoint:

```json
{
    "@odata.id": "/redfish/v1/Chassis/1/Thermal",
    "@odata.type": "#Thermal.v1_7_0.Thermal",
    "Id": "Thermal",
    "Name": "Thermal",
    "Temperatures": [
        {
            "MemberId": "0",
            "Name": "CPU 1 Temp",
            "Status": { "State": "Enabled", "Health": "OK" },
            "ReadingCelsius": 45.0,
            "UpperThresholdNonCritical": 75.0,
            "UpperThresholdCritical": 85.0,
            "UpperThresholdFatal": 90.0
        },
        {
            "MemberId": "1",
            "Name": "Inlet Air Temp",
            "Status": { "State": "Enabled", "Health": "OK" },
            "ReadingCelsius": 22.0
        }
    ],
    "Fans": [
        {
            "MemberId": "0",
            "Name": "System Fan 1A",
            "Status": { "State": "Enabled", "Health": "OK" },
            "Reading": 4560,
            "ReadingUnits": "RPM",
            "LowerThresholdCritical": 840
        }
    ]
}
```

The Power endpoint (`/redfish/v1/Chassis/1/Power`) returns:

```json
{
    "PowerControl": [
        {
            "Name": "System Power Control",
            "PowerConsumedWatts": 312.0,
            "PowerCapacityWatts": 750.0
        }
    ]
}
```


---

## 2. Elasticsearch Transformations (Redfish)

### 2. Lenovo Servers (Redfish JSON → Elasticsearch)

**Before** (raw Redfish nested JSON array):
```json
{
    "Temperatures": [
        { "Name": "CPU 1 Temp", "ReadingCelsius": 45.0, "Status": { "Health": "OK" } }
    ],
    "Fans": [
        { "Name": "System Fan 1A", "Reading": 4560, "ReadingUnits": "RPM" }
    ]
}
```

**After** (stored in `telegraf-metrics-2026.04.10`):
```json
{
    "@timestamp": "2026-04-10T07:30:00.000Z",
    "measurement_name": "server_redfish",
    "server_redfish": {
        "Temperatures_CPU_1_Temp_ReadingCelsius": 45.0,
        "Temperatures_CPU_1_Temp_Health": "OK",
        "Fans_System_Fan_1A_Reading": 4560,
        "PowerConsumedWatts": 312.0
    },
    "tag": {
        "host": "server-HCI-01",
        "address": "10.50.0.2"
    }
}
```

| Transformation Applied | Detail |
|---|---|
| Array flattening | `Temperatures[0]` → `Temperatures_CPU_1_Temp_*` |
| Nested object flattening | `Status.Health` → `Health` (inline) |
| Tag injection | `host` label added from telegraf config per-server block |


---

## 3. All Available Metrics (Redfish)

## 2. Lenovo Servers — All Available Redfish Fields

**Model:** Lenovo ThinkSystem (XCC BMC: `XCC-7D76-J901GKXY`)  
**Redfish Version:** 1.16.0  
**Auth:** Basic Auth, user: `hndept`

### 2.1 System Overview (`/redfish/v1/Systems/1`)

| Status | Field | Type | Current Value | Description |
|---|---|---|---|---|
| ✅ | `Status.Health` | String | `OK` | Overall system health |
| ✅ | `Status.HealthRollup` | String | `OK` | Rolled-up health including subsystems |
| ✅ | `Status.State` | String | `Enabled` | System operational state |
| ✅ | `PowerState` | String | `On` | Current power state |
| ⬜ | `HostName` | String | `XCC-7D76-J901GKXY` | System/BMC hostname |
| ⬜ | `Manufacturer` | String | `Lenovo` | Hardware manufacturer |
| ⬜ | `SKU` | String | `7D76CTO1WW` | System SKU/part number |
| ⬜ | `IndicatorLED` | String | `Off` | Front panel LED (Off/Blinking/Lit) |
| ⬜ | `MemorySummary.TotalSystemMemoryGiB` | Float | — | Total installed RAM (GiB) |
| ⬜ | `MemorySummary.Status.Health` | String | — | Memory subsystem health |
| ⬜ | `ProcessorSummary.Count` | Integer | — | Number of physical processor sockets |
| ⬜ | `ProcessorSummary.Model` | String | — | CPU model name |
| ⬜ | `ProcessorSummary.Status.Health` | String | — | CPU subsystem health |
| ⬜ | `BiosVersion` | String | — | Current BIOS version string |

### 2.2 Thermal — Temperatures (`/redfish/v1/Chassis/1/Thermal`)

These fields repeat per sensor. Real sensor names confirmed from live device:

| Status | Sensor Name | Field | Unit | Thresholds Available |
|---|---|---|---|---|
| ✅ | Ambient Temp | `ReadingCelsius` | °C | NonCritical: 43°C |
| ⬜ | Exhaust Temp | `ReadingCelsius` | °C | NonCritical, Critical |
| ⬜ | CPU 1 Temp | `ReadingCelsius` | °C | NonCritical, Critical, Fatal |
| ⬜ | CPU 2 Temp | `ReadingCelsius` | °C | NonCritical, Critical, Fatal |
| ⬜ | DIMM Temps (per slot) | `ReadingCelsius` | °C | Critical, Fatal |
| ⬜ | PCIe Slot Temps | `ReadingCelsius` | °C | NonCritical |

Per-sensor sub-fields available:

| Status | Sub-field | Type | Description |
|---|---|---|---|
| ✅ | `ReadingCelsius` | Float | Current sensor temperature |
| ✅ | `Status.Health` | String | `OK` / `Warning` / `Critical` |
| ⬜ | `UpperThresholdNonCritical` | Float | Warning threshold |
| ⬜ | `UpperThresholdCritical` | Float | Alert threshold |
| ⬜ | `UpperThresholdFatal` | Float | Shutdown threshold |

### 2.3 Thermal — Fans (`/redfish/v1/Chassis/1/Thermal`)

All 8 system fans confirmed present. Example: `Fan 1 Front Tach` reading `8610 RPM`.

| Status | Sub-field | Unit | Description |
|---|---|---|---|
| ✅ | `Reading` | RPM | Current fan speed |
| ✅ | `Status.Health` | String | Fan health state |
| ⬜ | `LowerThresholdCritical` | RPM | Minimum safe speed (e.g. 984 RPM) |
| ⬜ | `MaxReadingRange` | RPM | Maximum physical range (e.g. 20910 RPM) |
| ⬜ | `HotPluggable` | Boolean | Whether fan can be replaced live |

### 2.4 Power (`/redfish/v1/Chassis/1/Power`)

| Status | Field | Unit | Current Value | Description |
|---|---|---|---|---|
| ✅ | `PowerControl[0].PowerConsumedWatts` | W | — | Real-time power draw |
| ⬜ | `PowerControl[0].PowerCapacityWatts` | W | `1320` | Maximum rated capacity |
| ⬜ | `PowerControl[0].PowerRequestedWatts` | W | `529` | Current power being requested |
| ⬜ | `PowerControl[0].PowerMetrics.AverageConsumedWatts` | W | `286` | 1-min average consumption |
| ⬜ | `PowerControl[0].PowerMetrics.MaxConsumedWatts` | W | `307` | Peak in interval |
| ⬜ | `PowerControl[0].PowerMetrics.MinConsumedWatts` | W | `266` | Minimum in interval |
| ⬜ | `PowerControl[0].Oem.Lenovo.PowerUtilization.GuaranteedInWatts` | W | `502` | Guaranteed minimum power delivery |
| ⬜ | `PowerSupplies[*].Status.Health` | String | — | PSU health state |
| ⬜ | `PowerSupplies[*].PowerOutputWatts` | W | — | Per-PSU actual output |
| ⬜ | `PowerSupplies[*].LineInputVoltage` | V | — | Input voltage to each PSU |
| ⬜ | `PowerSupplies[*].Model` | String | — | PSU model number |

### 2.5 Storage (`/redfish/v1/Systems/1/Storage`)

| Status | Field | Type | Description |
|---|---|---|---|
| ⬜ | `Members` (walk) | Array | List of storage controllers |
| ⬜ | `StorageControllers[*].Status.Health` | String | RAID controller health |
| ⬜ | `StorageControllers[*].SpeedGbps` | Float | Controller bus speed |
| ⬜ | `Drives[*].Status.Health` | String | Per-disk health |
| ⬜ | `Drives[*].CapacityBytes` | Integer | Disk capacity in bytes |
| ⬜ | `Drives[*].PredictedMediaLifeLeftPercent` | Integer | SSD wear indicator |
| ⬜ | `Drives[*].RotationSpeedRPM` | Integer | HDD spindle speed |

### 2.6 Manager / BMC (`/redfish/v1/Managers/1`)

| Status | Field | Type | Description |
|---|---|---|---|
| ⬜ | `PowerState` | String | BMC power state |
| ⬜ | `FirmwareVersion` | String | XCC firmware version |
| ⬜ | `Status.Health` | String | BMC health state |
| ⬜ | `Oem.Lenovo.release_name` | String | Release name (e.g. `egs_gp_23-5`) |

