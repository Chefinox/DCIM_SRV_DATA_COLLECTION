# Redfish HTTP Metrics List — Comprehensive Reference

Dokumen ini mencantumkan semua metrik yang dapat diambil dari server (Lenovo ThinkSystem) menggunakan plugin `inputs.http` Telegraf melalui API Redfish. Berbeda dengan plugin standar, metode ini memungkinkan kita mengambil data inventaris dan detail sistem yang lebih mendalam dari tiga endpoint utama.

---

## 1. System Inventory & Identity (Primary)
**Endpoint:** `/redfish/v1/Systems/1`

| Field Name | Type | Deskripsi |
| :--- | :--- | :--- |
| `SerialNumber` | String | Factory Serial Number |
| `HostName` | String | BMC/XCC System Hostname |
| `BiosVersion` | String | Active BIOS/UEFI version |
| `PowerState` | String | Power status (`On`, `Off`) |

---

## 2. Chassis Inventory (Hardware Level)
**Endpoint:** `/redfish/v1/Chassis/1`

| Field Name | Type | Deskripsi |
| :--- | :--- | :--- |
| `Model` | String | Machine Type / Model (MTM) - misal: `7D9ACTO1WW` |
| `Oem_Lenovo_ProductName` | String | Friendly Device Name - misal: `ThinkSystem SR665 V3` |

---

## 3. Manager Inventory (Controller Level)
**Endpoint:** `/redfish/v1/Managers/1`

| Field Name | Type | Deskripsi |
| :--- | :--- | :--- |
| `FirmwareVersion` | String | BMC/XCC Primary Firmware Version |
| `ManagerType` | String | Controller Type (BMC) |

---

## 4. Resource Summary (Capacity)
**Endpoint:** `/redfish/v1/Systems/1`

| Field Name | Type | Deskripsi |
| :--- | :--- | :--- |
| `ProcessorSummary_Count` | Int | Total physical CPUs |
| `ProcessorSummary_LogicalProcessorCount` | Int | Total Threads (Logical) |
| `MemorySummary_TotalSystemMemoryGiB` | Int | Total RAM (GiB) |

---

## Cara Implementasi di Telegraf
Untuk mengambil metrik ini secara optimal, kita menggunakan multiple URLs dalam satu blok input:

```toml
[[inputs.http]]
  urls = [
    "https://10.50.0.x/redfish/v1/Systems/1",
    "https://10.50.0.x/redfish/v1/Chassis/1",
    "https://10.50.0.x/redfish/v1/Managers/1"
  ]
  username = "hndept"
  password = 'F!tech@0918'
  insecure_skip_verify = true
  data_format = "json"
  name_override = "server_inventory"
  
  json_string_fields = [
    "Model", "Oem_Lenovo_ProductName", "SerialNumber", 
    "FirmwareVersion", "HostName", "PowerState"
  ]
  json_fields = [
    "ProcessorSummary_Count", "MemorySummary_TotalSystemMemoryGiB"
  ]
```

> **Note:** Telegraf akan menggabungkan data dari ketiga endpoint ini ke dalam satu *measurement* `server_inventory` berdasarkan timestamp dan tags yang sama.

---
_Terakhir diperbarui: 2026-04-16 (Standardized Inventory Schema)_
