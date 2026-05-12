# 05 - Universal Metrics Overview (Clean Naming)

Dokumen ini mendefinisikan 8 poin metadata universal yang wajib ada di setiap dokumen Elasticsearch untuk seluruh kategori infrastruktur.

## 📋 Universal 8-Points Metadata

Semua field di bawah ini diindeks sebagai **Keyword Tags** untuk memungkinkan filter lintas index yang sangat cepat.

| # | Field Name | Description | Example Value |
|:---|:---|:---|:---|
| 1 | `model` | Model/Tipe Perangkat | `7D76CTO1WW`, `RS2423RP+` |
| 2 | `serial_number` | Serial Number (Primary Key) | `J901F8KE`, `9E2133T16585` |
| 3 | `hostname` | Nama Perangkat/Identity | `FIT-Core-SW`, `UPS Agent` |
| 4 | `firmware` | Versi Firmware/BIOS/OS | `7.16.2`, `V6.042/040` |
| 5 | `ip` | Management IP Address | `10.50.0.5`, `192.168.1.254` |
| 6 | `device_type` | Kategori Perangkat | `server`, `ups`, `mikrotik`, `cctv` |
| 7 | `category` | Grup Infrastruktur | `infrastructure`, `security` |
| 8 | `@timestamp` | Waktu Data Diambil (Injected) | `2026-04-17T09:30:00Z` |

---

## ��️ Cara Penggunaan di Kibana

Gunakan filter `tag` untuk menemukan data spesifik lintas platform:

- **Filter by Serial:** `tag.serial_number : "J901F8KE"`
- **Filter by Group:** `tag.category : "infrastructure"`
- **Filter by IP:** `tag.ip : "172.16.35.1"`

---

## 🔄 Mapping Source (Raw to Standard)

| Standard | APC UPS | Lenovo Server | MikroTik | Hikvision | Synology NAS |
|:---|:---|:---|:---|:---|:---|
| **model** | `ups_apc.model` | `Model` (MTM) | `sysDescr` | `deviceInfo.model` | `nas_inventory.model` |
| **serial_number** | `ups_apc.sn` | `SerialNumber` | `snmp.serial` | `deviceInfo.sn` | `nas_inventory.sn` |
| **hostname** | `ups_apc.name` | `HostName` | `sysName` | `deviceInfo.name` | `nas_inventory.host` |
| **firmware** | `ups_apc.fw` | `FirmwareVersion` | `firmware_version`| `deviceInfo.fw` | `nas_inventory.fw` |
| **ip** | `agent_host` | `address` | `agent_host` | `ip` | `ip` |
