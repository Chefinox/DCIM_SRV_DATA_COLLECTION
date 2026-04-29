# All Available Metrics — Complete Reference

> Semua metric di dokumen ini telah **diuji langsung** dan mengeluarkan hasil.  
> Status diverifikasi langsung dari Elasticsearch dan raw API responses.

---

## 📌 Legend

| Symbol | Keterangan |
| :---: | :--- |
| ✅ | **Dikonfigurasi** — Aktif diambil Telegraf, terverifikasi ada di Elasticsearch |
| ⬜ | **Tersedia** — Device bisa mengeluarkan data ini, **belum dikonfigurasi** |
| ⚠️ | **Butuh Setup Tambahan** — Memerlukan konfigurasi di sisi device (SNMP, plugin, dll) |

---

## 📊 Ringkasan Coverage

| Device | Protocol | Index | Total Tersedia | Dikonfigurasi |
| :--- | :--- | :--- | :---: | :---: |
| **Unified Assets (All Devices)** | **Python (Exec)** | **`dcim-inventory-*`** | **33** | **32** ✅ |
| APC UPS 30KH | SNMPv3 | `telegraf-ups-*` | 31 | **31** ✅ |
| Lenovo Server (Redfish Sensor) | HTTPS REST | `telegraf-server-*` | ~30 sensor | **17** ✅ |
| Lenovo Server (HTTP Inventory) | HTTPS REST | `telegraf-server-*` | ~15 fields | **10** ✅ |
| MikroTik Switches | SNMPv2c | `telegraf-mikrotik-*` | 28+ | **20** ✅ |
| Hikvision NVR | ISAPI/HTTP | `cctv-metrics-*` | 25+ | **3** ✅ |
| Hikvision CCTV Camera | ISAPI/HTTP | `cctv-metrics-*` | 20+ | **11** ✅ |

---

## 1. APC UPS — SNMP Metrics

**Model:** APC 30KH (3-phase industrial UPS)  
**Protocol:** SNMPv3 — user: `hndept`, SHA + AES  
**Index:** `telegraf-ups-*` | **Filter:** `tag.device_type : "ups"`  
**Config:** `/etc/telegraf/telegraf.d/ups-apc.conf`

### 1.1 System Identity (MIB-II `.1.3.6.1.2.1.1.*`)

| Status | ES Field | OID | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `system_name` | `.1.3.6.1.2.1.1.5.0` | `"UPS Agent"` | Nama jaringan kartu network UPS |
| ✅ | `system_location` | `.1.3.6.1.2.1.1.6.0` | `"PT Falah Inovasi Teknologi"` | Lokasi fisik perangkat |
| ✅ | `system_contact` | `.1.3.6.1.2.1.1.4.0` | `"Administrator"` | Kontak penanggung jawab |
| ✅ | `system_uptime` | `.1.3.6.1.2.1.1.3.0` | `1621040053` (ticks) | Uptime sejak reboot network card |
| ✅ | `system_description` | `.1.3.6.1.2.1.1.1.0` | `"UPS Agent"` | Deskripsi hardware umum |

### 1.2 OEM MIB — UPS Health (`.1.3.6.1.4.1.935.*`)

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `ups_apc.model` | `.1.3.6.1.4.1.935.1.1.1.1.1.1.0` | String | `"30KH"` | Model UPS |
| ✅ | `ups_apc.status` | `.1.3.6.1.4.1.935.1.1.1.4.1.1.0` | Enum | `2` | `2`=OnLine, `3`=OnBattery, `6`=ByPass |
| ✅ | `ups_apc.battery_capacity` | `.1.3.6.1.4.1.935.1.1.1.2.2.1.0` | % | `100` | Level charge baterai |
| ✅ | `ups_apc.battery_temp` | `.1.3.6.1.4.1.935.1.1.1.2.2.2.0` | °C | `0` | Suhu internal baterai |
| ✅ | `ups_apc.battery_runtime_remain` | `.1.3.6.1.4.1.935.1.1.1.2.2.3.0` | Min | `219` | Estimasi runtime tersisa |
| ✅ | `ups_apc.input_voltage` | `.1.3.6.1.4.1.935.1.1.1.3.2.1.0` | 0.1V | `2281` (=228.1V) | Tegangan input AC (L1) |
| ✅ | `ups_apc.output_voltage` | `.1.3.6.1.4.1.935.1.1.1.4.2.1.0` | 0.1V | `2310` (=231.0V) | Tegangan output AC (L1) |
| ✅ | `ups_apc.output_load` | `.1.3.6.1.4.1.935.1.1.1.4.2.3.0` | % | `0` | Beban output dari kapasitas penuh |

### 1.3 RFC 1628 UPS MIB — Identity (`.1.3.6.1.2.1.33.1.1.*`)

| Status | ES Field | OID | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `serial_number` | `.1.3.6.1.2.1.33.1.1.1.0` | `"9E2133T16585"` | Serial number pabrik |
| ✅ | `firmware_version` | `.1.3.6.1.2.1.33.1.1.3.0` | `"V6.042/040"` | Versi firmware utama |
| ✅ | `agent_firmware` | `.1.3.6.1.2.1.33.1.1.4.0` | `"3.7.DA807.APC.15"` | Firmware network agent card |

### 1.4 RFC 1628 — Battery Detail (`.1.3.6.1.2.1.33.1.2.*`)

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `battery_status` | `.1.3.6.1.2.1.33.1.2.1.0` | Enum | `2` (Normal) | `2`=Normal, `3`=Low, `4`=Depleted |
| ✅ | `battery_seconds_on_battery` | `.1.3.6.1.2.1.33.1.2.2.0` | Sec | `0` | Durasi berjalan di baterai |
| ✅ | `battery_voltage` | `.1.3.6.1.2.1.33.1.2.5.0` | 0.1V | `2680` (=268.0V) | Tegangan bank baterai |
| ✅ | `battery_current` | `.1.3.6.1.2.1.33.1.2.6.0` | A | `1` | Arus baterai (positif = charging) |

### 1.5 RFC 1628 — Input 3-Phase (`.1.3.6.1.2.1.33.1.3.*`)

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `input_frequency_L1` | `.1.3.6.1.2.1.33.1.3.3.1.2.1` | 0.1Hz | `500` (=50.0Hz) | Frekuensi input Phase L1 |
| ✅ | `input_frequency_L2` | `.1.3.6.1.2.1.33.1.3.3.1.2.2` | 0.1Hz | `500` | Frekuensi input Phase L2 |
| ✅ | `input_frequency_L3` | `.1.3.6.1.2.1.33.1.3.3.1.2.3` | 0.1Hz | `500` | Frekuensi input Phase L3 |
| ✅ | `input_voltage_L1` | `.1.3.6.1.2.1.33.1.3.3.1.3.1` | V | `228` | Tegangan input Phase L1 |
| ✅ | `input_voltage_L2` | `.1.3.6.1.2.1.33.1.3.3.1.3.2` | V | `222` | Tegangan input Phase L2 |
| ✅ | `input_voltage_L3` | `.1.3.6.1.2.1.33.1.3.3.1.3.3` | V | `225` | Tegangan input Phase L3 |

### 1.6 RFC 1628 — Output 3-Phase (`.1.3.6.1.2.1.33.1.4.*`)

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `output_frequency` | `.1.3.6.1.2.1.33.1.4.2.0` | 0.1Hz | `499` (=49.9Hz) | Frekuensi output |
| ✅ | `output_voltage_L1` | `.1.3.6.1.2.1.33.1.4.4.1.2.1` | V | `231` | Tegangan output Phase L1 |
| ✅ | `output_voltage_L2` | `.1.3.6.1.2.1.33.1.4.4.1.2.2` | V | `231` | Tegangan output Phase L2 |
| ✅ | `output_voltage_L3` | `.1.3.6.1.2.1.33.1.4.4.1.2.3` | V | `231` | Tegangan output Phase L3 |
| ✅ | `output_current_L1` | `.1.3.6.1.2.1.33.1.4.4.1.3.1` | A | `0` | Arus output Phase L1 |
| ✅ | `output_current_L2` | `.1.3.6.1.2.1.33.1.4.4.1.3.2` | A | `0` | Arus output Phase L2 |
| ✅ | `output_current_L3` | `.1.3.6.1.2.1.33.1.4.4.1.3.3` | A | `0` | Arus output Phase L3 |
| ✅ | `output_load_L1` | `.1.3.6.1.2.1.33.1.4.4.1.5.1` | % | `2` | Beban output Phase L1 |
| ✅ | `output_load_L2` | `.1.3.6.1.2.1.33.1.4.4.1.5.2` | % | `10` | Beban output Phase L2 |
| ✅ | `output_load_L3` | `.1.3.6.1.2.1.33.1.4.4.1.5.3` | % | `3` | Beban output Phase L3 |

---

## 2. Lenovo Server — Redfish Metrics

**Model:** Lenovo ThinkSystem SR650/SR665 V3 (via XCC BMC)  
**Protocol:** HTTPS Redfish API  
**Index:** `telegraf-server-*` | **Filter:** `tag.device_type : "server"`

### 2.1 Sensor Health via `inputs.redfish` Plugin

**Config:** `/etc/telegraf/telegraf.d/server-redfish.conf`  
**Measurement:** `server_redfish`

#### 2.1.1 Power Metrics

| Status | ES Field | `tag.name` | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `server_redfish.power_output_watts` | `"PSU1"` / `"PSU2"` | W | `130` | Output daya nyata PSU |
| ✅ | `server_redfish.power_input_watts` | — | W | `122` | Input daya dari PLN ke PSU |
| ✅ | `server_redfish.line_input_voltage` | — | V | `220` | Tegangan input AC PSU |
| ✅ | `server_redfish.power_capacity_watts` | — | W | `1800` | Kapasitas maksimum PSU |

#### 2.1.2 Thermal Sensors (filter `tag.name`)

| Status | ES Field | `tag.name` | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `server_redfish.reading_celsius` | `"Ambient Temp"` | °C | `16` | Suhu udara masuk chassis |
| ✅ | `server_redfish.reading_celsius` | `"Exhaust Temp"` | °C | `28` | Suhu udara keluar chassis |
| ✅ | `server_redfish.reading_celsius` | `"CPU 1 Temp"` | °C | `30` | Suhu processor Socket 1 |
| ✅ | `server_redfish.reading_celsius` | `"CPU 2 Temp"` | °C | `28` | Suhu processor Socket 2 |
| ✅ | `server_redfish.reading_celsius` | `"CPU 1 DTS"` | °C | `57` | Digital Thermal Sensor CPU 1 |
| ✅ | `server_redfish.reading_celsius` | `"CPU 2 DTS"` | °C | `55` | Digital Thermal Sensor CPU 2 |
| ✅ | `server_redfish.reading_celsius` | `"PCH Temp"` | °C | `45` | Suhu Platform Controller Hub |
| ✅ | `server_redfish.reading_celsius` | `"DIMM X Temp"` | °C | `22–23` | Suhu slot DIMM individual |

#### 2.1.3 Cooling Metrics (Fan Tach)

| Status | ES Field | `tag.name` | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `server_redfish.reading_rpm` | `"Fan 1 Front Tach"` | RPM | `7134` | Kecepatan Fan 1 (depan) |
| ✅ | `server_redfish.reading_rpm` | `"Fan X Rear Tach"` | RPM | `6825` | Kecepatan Fan X (belakang) |
| ⬜ | `server_redfish.reading_percent` | `"CPU Utilization"` | % | *tidak tersedia via endpoint ini* | CPU Load (hanya via IPMI/SNMP) |

#### 2.1.4 Voltage Sensors

| Status | ES Field | `tag.name` | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `server_redfish.reading_volts` | `"SysBrd 12V"` | V | `12.2` | Rail 12V motherboard |
| ✅ | `server_redfish.reading_volts` | `"SysBrd 5V"` | V | `5.1` | Rail 5V motherboard |
| ✅ | `server_redfish.reading_volts` | `"SysBrd 3.3V"` | V | `3.3` | Rail 3.3V motherboard |

### 2.2 Inventory via `inputs.http` Plugin (Multi-Endpoint)

**Config:** `/etc/telegraf/telegraf.d/server-redfish-inventory.conf`  
**Measurement:** `server_inventory`

#### 2.2.1 Dari `/redfish/v1/Chassis/1`

| Status | ES Field | Type | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `server_inventory.Model` | String | `"7D9ACTO1WW"` | Machine Type / Model (MTM) |
| ✅ | `server_inventory.Oem_Lenovo_ProductName` | String | `"ThinkSystem SR665 V3"` | Nama produk ramah pengguna |
| ✅ | `server_inventory.SerialNumber` | String | `"J901F8KE"` | Serial number pabrik chassis |
| ✅ | `server_inventory.PowerState` | String | `"On"` | Status daya chassis |
| ✅ | `server_inventory.Status_Health` | String | `"OK"` | Kesehatan chassis agregat |

#### 2.2.2 Dari `/redfish/v1/Systems/1`

| Status | ES Field | Type | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `server_inventory.SerialNumber` | String | `"J901F8KE"` | Serial number sistem |
| ✅ | `server_inventory.HostName` | String | `"XCC-7D9A-J901F8KE"` | Nama host BMC/XCC |
| ✅ | `server_inventory.BiosVersion` | String | `"KAE116K"` | Versi BIOS/UEFI (info tambahan) |
| ✅ | `server_inventory.PowerState` | String | `"On"` | Status daya sistem |
| ✅ | `server_inventory.MemorySummary_TotalSystemMemoryGiB` | Int | `128` / `256` | Total RAM terpasang (GiB) |
| ✅ | `server_inventory.ProcessorSummary_Count` | Int | `2` | Jumlah physical CPU |
| ✅ | `server_inventory.ProcessorSummary_LogicalProcessorCount` | Int | `64–96` | Total thread (logical) |
| ✅ | `server_inventory.Oem_Lenovo_TotalPowerOnHours` | Int | `16995` | Akumulasi jam operasional hardware |

#### 2.2.3 Dari `/redfish/v1/Managers/1`

| Status | ES Field | Type | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `server_inventory.FirmwareVersion` | String | `"ESX322I 3.92 2024-01-29"` | **Firmware BMC/XCC Primary** |
| ⬜ | `server_inventory.ManagerType` | String | `"BMC"` | Tipe controller (tersedia, tidak diparsing) |

#### 2.2.4 Belum Dikonfigurasi

| Status | Sumber | Deskripsi | Catatan |
| :---: | :--- | :--- | :--- |
| ⚠️ | SNMP (XCC) | CPU Utilization (%) | Perlu aktifkan SNMP agent di XCC Web UI |
| ⬜ | `/redfish/v1/Systems/1/ProcessorSummary/ProcessorMetrics` | CPU BandwidthPercent | Tersedia via Redfish, belum dikonfigurasi polling-nya |

---

## 3. Hikvision Security System

**Protocol:** ISAPI/HTTP (Python Script)  
**Index:** `cctv-metrics-*`  
**Config:** `/home/infra/dcim_metrics_project/scripts/hikvision_poller.py`

### 3.1 NVR (192.168.1.254)

> **Status Terbaru:** NVR sudah berhasil diotentikasi dan datanya sukses diindeks ke Elasticsearch.

| Status | ES Field | Sumber ISAPI | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `device` | (hardcoded) | `"Hikvision-NVR"` | Label perangkat |
| ✅ | `ip` | (hardcoded) | `"192.168.1.254"` | Alamat IP NVR |
| ✅ | `device_info.model` | `/ISAPI/System/deviceInfo` | `"DS-7732NI-K4"` | Model NVR hardware |
| ✅ | `device_info.serialNumber` | `/ISAPI/System/deviceInfo` | `"DS-7732NI-K4162022..."`| Serial number pabrik |
| ✅ | `device_info.firmwareVersion` | `/ISAPI/System/deviceInfo` | `"V4.72.107"` | Versi firmware NVR |
| ✅ | `system_status.deviceUpTime` | `/ISAPI/System/status` | `"39094390"` | Uptime sejak reboot |
| ✅ | `system_status.CPUList.CPU.cpuUtilization` | `/ISAPI/System/status` | `"0"` | Utilisasi CPU NVR (%) |
| ✅ | `system_status.MemoryList.Memory.memoryUsage` | `/ISAPI/System/status` | `"774.656250"` | Pemakaian RAM NVR (MB/%) |
| ✅ | `storage.hdd[0].status` | `/ISAPI/ContentMgmt/Storage/hdd` | `"idle"` / `"ok"` | Status HDD rekaman |
| ✅ | `storage.hdd[0].freeSpace` | `/ISAPI/ContentMgmt/Storage/hdd` | `"0"` | Ruang HDD tersisa (MB) |

### 3.2 IP Camera (192.168.1.2 – 192.168.1.33)

> Data kamera diambil langsung per-IP, **bukan** melalui NVR.

| Status | ES Field | Sumber ISAPI | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `ip` | (hardcoded) | `"192.168.1.x"` | Alamat IP kamera |
| ✅ | `status` | (ping/ISAPI check) | `"Online"` / `"Offline"` | Status konektivitas |
| ✅ | `device_type` | (hardcoded) | `"CCTV"` | Tipe perangkat |
| ✅ | `device_info.deviceName` | `/ISAPI/System/deviceInfo` | `"IP CAMERA"` | Nama konfigurasi kamera |
| ✅ | `device_info.model` | `/ISAPI/System/deviceInfo` | `"DS-2CD1143G0E-I"` | Model hardware kamera |
| ✅ | `device_info.serialNumber` | `/ISAPI/System/deviceInfo` | `"DS-2CD1143...406460"` | Serial number |
| ✅ | `device_info.macAddress` | `/ISAPI/System/deviceInfo` | `"08:a1:89:xx:xx"` | MAC address |
| ✅ | `device_info.firmwareVersion` | `/ISAPI/System/deviceInfo` | `"V5.5.114"` | Versi firmware kamera |
| ✅ | `system_status.currentDeviceTime` | `/ISAPI/System/status` | `"2026-04-12T06:59..."` | Waktu saat ini di kamera |
| ✅ | `system_status.deviceUpTime` | `/ISAPI/System/status` | `"38694089"` (sec) | Uptime kamera |
| ✅ | `system_status.CPUList.CPU.cpuUtilization` | `/ISAPI/System/status` | `"30"` (%) | CPU load SoC kamera |
| ✅ | `system_status.MemoryList.Memory.memoryUsage` | `/ISAPI/System/status` | `"93"` (%) | RAM usage kamera |
| ✅ | `system_status.MemoryList.Memory.memoryAvailable` | `/ISAPI/System/status` | `"4408"` (MB) | RAM tersisa |
| ⬜ | `StreamingChannel.bitrate` | `/ISAPI/Streaming/channels` | — | Bitrate video real-time |
| ⬜ | `VideoInputChannel.resDesc` | `/ISAPI/System/Video/inputs` | — | Resolusi video |

---

## 4. MikroTik Switches — SNMP Metrics

**Protocol:** SNMPv2c — community: `public`  
**Index:** `telegraf-mikrotik-*` | **Filter:** `tag.device_type : "mikrotik"`  
**Config:** `/etc/telegraf/telegraf.d/mikrotik-snmp.conf`

### 4.1 System Identity (MIB-II `.1.3.6.1.2.1.1.*`)

| Status | ES Field | OID | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- |
| ✅ | `mikrotik.system_name` | `.1.3.6.1.2.1.1.5.0` | `"MikroTik-Switch-02"` | Hostname switch |
| ✅ | `mikrotik.system_uptime` | `.1.3.6.1.2.1.1.3.0` | `14131023` (ticks) | Uptime sejak reboot |
| ✅ | `mikrotik.system_location` | `.1.3.6.1.2.1.1.6.0` | `"Server Room"` | Lokasi fisik |
| ✅ | `mikrotik.system_contact` | `.1.3.6.1.2.1.1.4.0` | `"IT Dept"` | Kontak admin |
| ✅ | `mikrotik.system_description` | `.1.3.6.1.2.1.1.1.0` | `"RouterOS CRS326-24G-2S+"` | Deskripsi hardware+OS |
| ✅ | `mikrotik.serial_number` | `.1.3.6.1.4.1.14988.1.1.7.3.0` | `"HC707RR1T60"` | Serial number pabrik |

### 4.2 CPU & Memory (MikroTik Private MIB)

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `mikrotik.cpu_load` | `.1.3.6.1.4.1.2021.11.10.0` | % | `5` | Rata-rata CPU load 1 menit |
| ✅ | `mikrotik.memory_total_kb` | `.1.3.6.1.2.1.25.2.3.1.5.65536` | KB | `2097152` | Total RAM |
| ✅ | `mikrotik.memory_used_kb` | `.1.3.6.1.2.1.25.2.3.1.6.65536` | KB | `524288` | RAM terpakai |
| ✅ | `mikrotik.disk_used_kb` | `.1.3.6.1.2.1.25.2.3.1.6.131072` | KB | `15620` | Storage flash terpakai |
| ✅ | `mikrotik.hdd_size_kb` | `.1.3.6.1.2.1.25.2.3.1.5.131072` | KB | `131072` | Total storage flash |
| ✅ | `mikrotik.cpu_frequency` | `.1.3.6.1.4.1.14988.1.1.3.14.0` | MHz | `2200` | Kecepatan clock CPU |

### 4.3 Interface Traffic per Port (`ifXTable`)

> Satu baris per port fisik (ether1…ether48, sfp1, sfp-sfpplus1, dll.)  
> **Measurement:** `interface` | **Tag:** `tag.ifName`

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `interface.if_name` | `.1.3.6.1.2.1.31.1.1.1.1` | String | `"ether1"` | Nama interface |
| ✅ | `interface.if_speed` | `.1.3.6.1.2.1.31.1.1.1.15` | bps | `1000000000` | Kecepatan link |
| ✅ | `interface.if_in_octets` | `.1.3.6.1.2.1.31.1.1.1.6` | bytes | `391608...` | Total bytes diterima |
| ✅ | `interface.if_out_octets` | `.1.3.6.1.2.1.31.1.1.1.10` | bytes | `423895...` | Total bytes dikirim |
| ✅ | `interface.if_in_errors` | `.1.3.6.1.2.1.2.2.1.14` | count | `0` | Paket error masuk |
| ✅ | `interface.if_out_errors` | `.1.3.6.1.2.1.2.2.1.20` | count | `0` | Paket error keluar |
| ✅ | `interface.if_in_discards` | `.1.3.6.1.2.1.2.2.1.13` | count | `0` | Paket drop masuk |
| ✅ | `interface.if_out_discards` | `.1.3.6.1.2.1.2.2.1.19` | count | `0` | Paket drop keluar |
| ✅ | `interface.if_in_ucast_pkts` | `.1.3.6.1.2.1.2.2.1.11` | count | `842942027` | Unicast paket masuk |
| ✅ | `interface.if_out_ucast_pkts` | `.1.3.6.1.2.1.2.2.1.17` | count | `888367566` | Unicast paket keluar |
| ✅ | `interface.if_oper_status` | `.1.3.6.1.2.1.2.2.1.8` | Enum | `1` | `1`=Up, `2`=Down |
| ✅ | `interface.if_admin_status` | `.1.3.6.1.2.1.2.2.1.7` | Enum | `1` | Status admin port |
| ✅ | `interface.if_last_change` | `.1.3.6.1.2.1.2.2.1.9` | Ticks | — | Waktu terakhir status berubah |

### 4.4 Hardware Health (MikroTik Private MIB)

| Status | ES Field | OID | Unit | Live Value | Deskripsi |
| :---: | :--- | :--- | :--- | :--- | :--- |
| ✅ | `mikrotik.cpu_temperature` | `.1.3.6.1.4.1.14988.1.1.3.100.1.3.17` | °C | `57` | Suhu CPU (CCR Router) |
| ✅ | `mikrotik.switch_temperature` | `.1.3.6.1.4.1.14988.1.1.3.100.1.3.51` | °C | `39` | Suhu board (CRS Switch) |
| ✅ | `mikrotik.sfp_temperature` | `.1.3.6.1.4.1.14988.1.1.3.100.1.3.50` | °C | `42` | Suhu modul SFP |
| ✅ | `mikrotik.board_temp1` | `.1.3.6.1.4.1.14988.1.1.3.100.1.3.7101` | °C | `45` | Sensor suhu mainboard |
| ✅ | `mikrotik.fan1_speed` | `.1.3.6.1.4.1.14988.1.1.3.100.1.3.7001` | RPM | `3990` | Kecepatan cooling fan |
| ✅ | `mikrotik.psu1_state` | `.1.3.6.1.4.1.14988.1.1.3.100.1.3.7401` | Enum | `1` | `1`=OK, `0`=Fail |

### 4.5 Wireless (MikroTik Private MIB — Hanya Perangkat WiFi)

> Saat ini tidak ada perangkat MikroTik WiFi (hanya switch), sehingga OID ini tidak berlaku.

| Status | ES Field | OID | Deskripsi |
| :---: | :--- | :--- | :--- |
| ⬜ | `wifi_clients_count` | `.1.3.6.1.4.1.14988.1.1.1.4.0` | Jumlah WiFi client aktif |
| ⬜ | `wifi_frequency` | `.1.3.6.1.4.1.14988.1.1.1.6.0` | Frekuensi radio (MHz) |
| ⬜ | `wifi_tx_power` | `.1.3.6.1.4.1.14988.1.1.23.3.0` | Daya transmit (dBm) |
| ⬜ | `wifi_noise_floor` | `.1.3.6.1.4.1.14988.1.1.1.21.0` | RF noise floor (dBm) |

---

_Terakhir diverifikasi: 2026-04-16 | Sumber: Live Elasticsearch + Raw API Response_
