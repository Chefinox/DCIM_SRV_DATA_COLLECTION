# Dashboard Kibana - Troubleshooting "No Results Found"

> **Last Updated**: 2026-05-21
> **Dashboard URL**: http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring

## 🔍 Masalah Umum

Dashboard menampilkan:
- **Blank putih** pada beberapa panel
- **"No results found"** pada visualisasi tertentu
- **Null values** pada metric panels

## ✅ Status Saat Ini (2026-05-20)

Semua panel sudah diperbaiki. Data tersedia untuk semua 6 device types:

| Device Type | Docs/Hour | Status | Key Fields |
|-------------|-----------|--------|------------|
| **network_switch** | ~4,700 | ✅ Working | `raw_fields.cpu_load`, `raw_fields.memory_used_kb` |
| **server** | ~4,700 | ✅ Working | `raw_fields.srv_reading_celsius`, `raw_fields.srv_power_watts` |
| **cctv** | ~720 | ✅ Working | `raw_fields.cpuUtilization`, `raw_fields.memoryUsage`, `raw_fields.status_online` |
| **nas** | ~1,050 | ✅ Working | `raw_fields.system_temp`, `raw_fields.diskTemp`, `raw_fields.volumeTotalBytes`, `raw_fields.volumeUsedBytes` |
| **nvr** | ~15 | ✅ Working | `raw_fields.cpuUtilization`, `raw_fields.memoryUsage`, `raw_fields.memoryUsagePct` |
| **ups** | ~15 | ✅ Working | `raw_fields.battery_capacity`, `raw_fields.output_load`, `raw_fields.output_voltage_L1/L2/L3` |

## ✅ Update Operasional (2026-05-21)

| Area | Status | Catatan |
| :--- | :---: | :--- |
| Threshold alerts | ✅ Active | `dcim-threshold-alerter.service` cek 6 rules tiap 120s |
| Stale-device alerts | ✅ Active | Missing event >30 menit masuk index `dcim-alerts` |
| Telegraf logging | ✅ Fixed | File log aktif: `/var/log/telegraf/telegraf.log` |
| Server inventory logging | ✅ Fixed | `logs/server_inventory.log` symlink ke `logs/server_inventory_to_pg.log` |
| Kafka short sampling | ⚠️ Interpret carefully | Sampling 3 detik bisa false warning karena collector interval 120 detik |

Kafka health lebih akurat dicek dari:

1. Topic offsets naik.
2. PostgreSQL `dcim_events` punya event baru.
3. Elasticsearch `dcim-metrics-unified-*` punya dokumen baru.
4. Service logs tidak error berulang.

## 🛠️ Fix History

### Fix 2026-05-20: Panel NVR/UPS/NAS Blank
**Root Cause**: Visualizations menggunakan field names lama (`dcim_metrics.raw_fields_xxx`, `tag.hostname`, `kafka_consumer.raw_fields_xxx`) yang tidak match dengan data aktual.

**Solution**: Update semua panel ke field names yang benar (`raw_fields.*`, `hostname.keyword`, `device_type.keyword`) dengan proper `match_phrase` filter.

**Script**: `/tmp/fix_kibana_panels_v4.py`

### Fix 2026-05-20: Pie Chart Device Types Tidak Tampil NVR/UPS
**Root Cause**: Metric `count` membuat NVR (60 docs) dan UPS (60 docs) terlalu kecil dibanding server (19,440 docs) — slice 0.13% tidak visible.

**Solution**: Ubah metric ke `cardinality(hostname.keyword)` — menampilkan jumlah device unik per tipe.

### Fix 2026-05-20: ES Disk Full → Index RED → No Results
**Root Cause**: Disk ES 92% penuh → flood stage block → index hari ini tidak bisa di-allocate.

**Solution**:
1. Hapus 11 old indices (05.03-05.14) → free ~4GB
2. Clear `read_only_allow_delete` block
3. Adjust watermark: flood_stage=95%, high=90%

### Fix 2026-05-20: NAS Storage Data Missing
**Root Cause**: Telegraf output namepass untuk `dcim.raw.storage.nas` tidak include `dcim_nas_volume` measurement.

**Solution**: Tambah `"dcim_nas_volume"` ke namepass di `/etc/telegraf/telegraf.conf` → restart telegraf.

## 🎯 Solusi

### 1. Panel yang Akan Bekerja

**Network Switch**:
- ✅ CPU Load (menggunakan `raw_fields.cpu_load`)
- ✅ Memory Usage (menggunakan `raw_fields.memory_used_kb`)
- ✅ Device count
- ❌ Interface status (tidak ada `ifOperStatus`)
- ❌ Traffic metrics (tidak ada `ifInOctets/ifOutOctets`)

**Server**:
- ✅ Temperature (menggunakan `raw_fields.reading_celsius`)
- ✅ Fan Speed (menggunakan `raw_fields.reading_rpm`)
- ✅ Power (menggunakan `raw_fields.power_input_watts`)
- ✅ Device count
- ❌ Health status (tidak ada `health` field)

**CCTV**:
- ✅ CPU Utilization (menggunakan `raw_fields.cpuUtilization`)
- ✅ Memory Usage (menggunakan `raw_fields.memoryUsage`)
- ✅ Status (menggunakan `raw_fields.status_text`)
- ✅ Device count
- ❌ Uptime (tidak ada `deviceUpTime`)
- ❌ Bitrate (tidak ada `outputBitrate`)

**UPS**:
- ❌ Semua panel (tidak ada data UPS dalam 1 jam terakhir)

### 2. Verifikasi Data

Jalankan script verifikasi:

```bash
cd /home/infra/dcim_metrics_project
python3 scripts/verify_dashboard_data.py
```

Output akan menunjukkan:
- Jumlah dokumen per device type
- Field yang tersedia
- Panel mana yang akan bekerja

### 3. Cek Field yang Tersedia

Untuk melihat field apa saja yang ada untuk device tertentu:

```bash
# Network Switch
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{"query":{"bool":{"must":[{"match":{"device_type":"network_switch"}},{"range":{"@timestamp":{"gte":"now-1h"}}}]}},"size":1}' \
  | jq '.hits.hits[0]._source.raw_fields | keys'

# Server
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{"query":{"bool":{"must":[{"match":{"device_type":"server"}},{"range":{"@timestamp":{"gte":"now-1h"}}}]}},"size":1}' \
  | jq '.hits.hits[0]._source.raw_fields | keys'

# CCTV
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{"query":{"bool":{"must":[{"match":{"device_type":"cctv"}},{"range":{"@timestamp":{"gte":"now-1h"}}}]}},"size":1}' \
  | jq '.hits.hits[0]._source.raw_fields | keys'
```

### 4. Update Dashboard untuk Field yang Ada

Dashboard sudah dibuat dengan field mapping yang benar untuk data yang tersedia:

**Working Panels**:
- Global Overview (device count, enrichment, severity, site) ✅
- Network Switch CPU & Memory ✅
- Server Temperature, Fan, Power ✅
- CCTV CPU, Memory, Status ✅
- Asset Inventory ✅

**Panels dengan "No Results"** (normal karena field tidak ada):
- Network interface details
- UPS metrics (no data)
- NAS disk details
- Server health status
- CCTV uptime/bitrate details

## 📊 Dashboard Status

### URL
http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard

### Expected Behavior

**✅ Panels yang Akan Menampilkan Data**:
1. Total Devices by Type (donut chart)
2. Enrichment Status
3. Severity Distribution
4. Devices by Site
5. Events Last Hour (pipeline health)
6. Network Switch CPU Load
7. Server Temperature
8. Server Fan Speed
9. CCTV CPU Utilization
10. CCTV Memory Usage
11. CCTV Status
12. Device tables (all categories)

**⚠️ Panels yang Akan Kosong** (expected):
- Interface traffic details (field tidak ada)
- UPS panels (no data)
- NAS disk temperature (field tidak ada)
- Server health status (field tidak ada)
- CCTV uptime/bitrate (field tidak ada)

## 🔧 Cara Memperbaiki

### Option 1: Terima "No Results" sebagai Normal

Ini adalah behavior yang expected karena:
- Tidak semua device mengirim semua metrics
- Beberapa field hanya ada di device tertentu
- UPS mungkin tidak aktif monitoring

### Option 2: Customize Dashboard

Edit `scripts/create_kibana_dashboard.py` dan hapus panel yang tidak diperlukan:

```python
# Comment out panels yang tidak ada datanya
# panels["p6_traffic_in"] = ...  # No ifInOctets data
# panels["p11_battery"] = ...     # No UPS data
```

Lalu regenerate:
```bash
python3 scripts/create_kibana_dashboard.py
```

### Option 3: Tambah Data Collection

Jika ingin panel tertentu bekerja, pastikan data collector mengirim field yang diperlukan:

**Untuk Interface Traffic**:
- Pastikan Telegraf/collector mengirim `ifInOctets`, `ifOutOctets`, `ifOperStatus`

**Untuk UPS**:
- Aktifkan UPS monitoring
- Pastikan SNMP collector berjalan untuk UPS

**Untuk CCTV Details**:
- Pastikan ISAPI collector mengirim `deviceUpTime`, `outputBitrate`

## 📝 Summary

**Status**: Dashboard **berhasil dibuat** dan **berfungsi untuk data yang tersedia**

**Working**:
- ✅ 24,560 dokumen dalam 1 jam terakhir
- ✅ 4 device types dengan data
- ✅ ~12 panels menampilkan data aktual
- ✅ Global overview berfungsi

**Expected "No Results"**:
- ⚠️ ~28 panels kosong karena field tidak ada (normal)
- ⚠️ UPS panels kosong karena no data (normal)

**Action Required**: **NONE** - Dashboard berfungsi sesuai data yang tersedia

---

**Last Updated**: 2026-05-20  
**Verified By**: Dashboard verification script
