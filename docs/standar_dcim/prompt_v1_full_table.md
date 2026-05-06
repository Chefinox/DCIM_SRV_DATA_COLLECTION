# Agent Prompt — Database Storage (Full Table, Semua raw_fields)
> **Versi**: A — Full Schema (Semua field sebagai kolom dedicated, tidak ada null yang disembunyikan)
> **Target DB**: PostgreSQL + Elasticsearch
> **Source**: dcim.enriched.events
> **Generated**: April 2026

---

## Konteks & Tujuan

Kamu adalah senior database engineer dengan akses SSH langsung ke server DCIM.

Tugasmu adalah membangun storage layer yang menyimpan **seluruh field** dari `dcim.enriched.events` ke dalam PostgreSQL dan Elasticsearch — mencakup semua device type yang aktif: **UPS, NAS, Network Switch, CCTV, dan Server**.

Setiap field dari `event_id` sampai `cached_at` harus muncul sebagai kolom dedicated di database. Field dari `raw_fields` tiap device type juga harus punya kolom masing-masing. Nilai null diperbolehkan untuk kolom device lain.

---

## Data Aktual per Device Type

### Device 1 — Network Switch (MikroTik)

**RAW** (`dcim.raw.network.interfaces`):
```json
{
  "name": "interface",
  "tags": {
    "host": "srv-rnd-dcim-consumer",
    "hostname": "FIT-DIST-SW-SERVER2",
    "ip": "172.16.35.6",
    "serial_number": "HEM08K3K7VW",
    "model": "RouterOS CRS312-4C+8XG",
    "firmware": "7.15.1"
  },
  "fields": {
    "ifAdminStatus": 1, "ifDescr": "combo3",
    "ifInOctets": 1555239067, "ifOperStatus": 1,
    "ifOutOctets": 3766575171, "ifSpeed": 0,
    "if_name": "combo3", "if_oper_status": 1
  },
  "timestamp": 1777347783
}
```

**ENRICHED** (`dcim.enriched.events`):
```json
{
  "event_id": "05d275f5-d672-45ca-aac4-6277894d177f",
  "event_time": "2026-04-28T03:43:03+00:00",
  "timestamp": 1777347783,
  "source_topic": "dcim.raw.network.interfaces",
  "measurement": "interface",
  "device_type": "network_switch",
  "hostname": "FIT-DIST-SW-SERVER2",
  "ip": "172.16.35.6",
  "serial_number": "HEM08K3K7VW",
  "metric_name": "interface_status",
  "metric_value": 1,
  "metric_unit": "status_code",
  "severity": "info",
  "raw_fields": {
    "ifAdminStatus": 1, "ifDescr": "combo3",
    "ifInOctets": 1555239067, "ifOperStatus": 1,
    "ifOutOctets": 3766575171, "ifSpeed": 0,
    "if_name": "combo3", "if_oper_status": 1,
    "ifMtu": 1500, "ifType": 6,
    "ifInErrors": 0, "ifOutErrors": 0,
    "ifInDiscards": 0, "ifOutDiscards": 0,
    "ifPhysAddress": "48:a9:8a:ed:79:41",
    "if_in_octets": 19595013676244,
    "if_out_octets": 33658671369801,
    "ifInUcastPkts": 3186145378,
    "ifOutUcastPkts": 2948942729
  },
  "raw_tags": {
    "firmware": "7.15.1", "hostname": "FIT-DIST-SW-SERVER2",
    "ifIndex": "12", "ip": "172.16.35.6",
    "model": "RouterOS CRS312-4C+8XG",
    "serial_number": "HEM08K3K7VW"
  },
  "site": "Local Instance",
  "rack_name": "Rack Server 2",
  "rack_position": 40,
  "room_name": "FIT-HeadOffice Room",
  "manufacturer": "MikroTik",
  "model": "CRS312-4C+8XG-RM",
  "asset_status": "in use",
  "environment": "Production",
  "business_unit": "IT Infrastructure Departement",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:46.174284",
  "cached_at": "2026-04-28T03:25:10.968253"
}
```

---

### Device 2 — UPS (APC)

**ENRICHED** (`dcim.enriched.events`):
```json
{
  "event_id": "d2a5e6fb-95a7-413f-8f72-af3d2ed6967f",
  "event_time": "2026-04-28T03:43:01+00:00",
  "timestamp": 1777347781,
  "source_topic": "dcim.raw.power.ups",
  "measurement": "ups_apc",
  "device_type": "ups",
  "hostname": "FALAH01-UPS-3Phase-30kVA",
  "ip": "192.168.100.140",
  "serial_number": "9E2133T16585",
  "metric_name": "battery_capacity",
  "metric_value": 100,
  "metric_unit": "percent",
  "severity": "info",
  "raw_fields": {
    "upsBatteryCapacity": 100,
    "upsBatteryRuntime": 506,
    "upsBatteryTemp": 23,
    "upsBatteryStatus": 2,
    "upsInputVoltage": 228,
    "upsOutputVoltage": 231,
    "upsOutputLoad": 2,
    "upsOutputFrequency": 500,
    "upsOutputStatus": 3,
    "upsSecondsOnBattery": 0,
    "upsFirmware": "V6.042/040",
    "upsModel": "30KH",
    "upsSerial": "9E2133T16585",
    "sysDescr": "UPS-FIT",
    "sysUpTime": 20871495
  },
  "raw_tags": {
    "device_type": "ups", "firmware": "V6.042/040",
    "hostname": "UPS-FIT", "ip": "192.168.100.140",
    "model": "30KH", "serial_number": "9E2133T16585"
  },
  "site": "Local Instance",
  "rack_name": "Ruang server",
  "rack_position": 1,
  "room_name": "FIT-HeadOffice Room",
  "manufacturer": "APC",
  "model": "APC Easy UPS 3S 30kVA 30kW (E3SUPS30KHB + E3SBT4)",
  "asset_status": "in use",
  "environment": "Production",
  "business_unit": "Facility Management Department",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:54.712660",
  "cached_at": "2026-04-28T03:25:10.949598"
}
```

---

### Device 3 — NAS (Synology)

**ENRICHED** (`dcim.enriched.events`):
```json
{
  "event_id": "891fd1cf-ef5b-47c1-a0b9-de5d0614dac9",
  "event_time": "2026-04-28T03:43:00+00:00",
  "timestamp": 1777347780,
  "source_topic": "dcim.raw.storage.nas",
  "measurement": "dcim_nas",
  "device_type": "nas",
  "hostname": "NAS-CD02",
  "ip": "10.50.0.110",
  "serial_number": "2270SBRXKZY8V",
  "metric_name": "disk_temperature",
  "metric_value": 30,
  "metric_unit": "celsius",
  "severity": "info",
  "raw_fields": {
    "diskModel": "WD40EFPX-68C6CN0",
    "diskStatus": 1,
    "diskTemp": 30,
    "diskID": "Disk 3",
    "system_temp": 33,
    "sysUpTime": 20871495,
    "sysDescr": "NAS-CD02"
  },
  "raw_tags": {
    "category": "storage", "device_type": "nas",
    "diskID": "Disk 3", "firmware": "DSM 7.2-72806",
    "hostname": "NAS-CD02", "ip": "10.50.0.110",
    "model": "DS920+", "serial_number": "2270SBRXKZY8V"
  },
  "site": "Local Instance",
  "rack_name": "Rack Server 2",
  "rack_position": 1,
  "room_name": "FIT-HeadOffice Room",
  "manufacturer": "Synology",
  "model": "DS220+",
  "asset_status": "in use",
  "environment": "Production",
  "business_unit": "IT Infrastructure Departement",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:54.341710",
  "cached_at": "2026-04-28T03:25:10.949088"
}
```

---

### Device 4 — CCTV (Hikvision) — PERLU PERBAIKAN

**ENRICHED** (`dcim.enriched.events`):
```json
{
  "event_id": "645a5cce-40e8-4442-8465-923e7a21f9e0",
  "event_time": "2026-04-27T20:43:00+00:00",
  "timestamp": 1777322580,
  "source_topic": "dcim.raw.device.isapi",
  "measurement": "cctv_metrics",
  "device_type": "cctv",
  "hostname": "unknown",
  "ip": "192.168.1.5",
  "serial_number": "NO_SN",
  "metric_name": "general_metric",
  "metric_value": null,
  "metric_unit": null,
  "severity": "info",
  "raw_fields": {
    "status_online": 0,
    "status_text": "Offline"
  },
  "raw_tags": {
    "hostname": "unknown", "ip": "192.168.1.5",
    "model": "unknown", "serial_number": "NO_SN"
  },
  "site": "FIT-Head-Office",
  "rack_name": "Unknown",
  "manufacturer": "Epson",
  "model": "WorkForce WF-7710",
  "enrichment_status": "NO_IDENTIFIER",
  "enrichment_match_method": "hostname_fallback",
  "enrichment_match_confidence": "low"
}
```

> ⚠️ **Bug Diketahui**: manufacturer = "Epson" dan model = "WorkForce WF-7710" adalah data printer
> yang masuk akibat hostname fallback dengan hostname "unknown". Data ini salah dan perlu diblokir.
> Serial number NO_SN dan hostname unknown harus ditandai khusus, bukan di-lookup ke CMDB.

---

### Device 5 — Server (Lenovo/Redfish) — BELUM ADA SAMPLE

> ⚠️ **Missing**: Belum ada contoh data server yang ter-enrich.
> Agent harus mencari sample dari Kafka sebelum membuat kolom server.

**Kolom server yang diperkirakan berdasarkan arsitektur Redfish:**
```
srv_sensor_name       VARCHAR(100)   -- nama sensor, e.g. "Inlet Temp"
srv_reading_celsius   NUMERIC(6,2)   -- suhu dalam celsius
srv_upper_critical    NUMERIC(6,2)   -- threshold critical
srv_upper_fatal       NUMERIC(6,2)   -- threshold fatal
srv_power_watts       NUMERIC(8,2)   -- konsumsi daya
srv_health            VARCHAR(50)    -- OK / Warning / Critical
srv_state             VARCHAR(50)    -- Enabled / Disabled
srv_firmware          VARCHAR(100)   -- versi firmware
srv_cpu_load          NUMERIC(5,2)   -- CPU load %
srv_memory_used_mb    BIGINT         -- memory used dalam MB
```

---

## STEP 1: Audit & Discovery

### 1a. Ambil sample server dari Kafka (WAJIB sebelum lanjut)
```bash
# Cari topic server
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --list --bootstrap-server localhost:9092 | grep -iE "server|redfish|ipmi"

# Sample enriched events dan filter device_type=server
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 100 --timeout-ms 20000 2>/dev/null \
  | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('device_type') in ('server','server_redfish','lenovo','dell','hp'):
            print(json.dumps(d, indent=2))
            break
    except: pass
"
```

**STOP di sini jika tidak ada data server. Report ke operator.**

### 1b. Audit semua device_type yang aktif
```bash
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 200 --timeout-ms 25000 2>/dev/null \
  | python3 -c "
import sys, json
seen = {}
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        dt = d.get('device_type','unknown')
        if dt not in seen:
            seen[dt] = {
                'measurement': d.get('measurement'),
                'raw_fields_keys': sorted(d.get('raw_fields',{}).keys()),
                'enrichment_status': d.get('enrichment_status'),
                'sample_hostname': d.get('hostname')
            }
    except: pass
print(json.dumps(seen, indent=2))
"
```

### 1c. Identifikasi CCTV yang masukkan data printer
```bash
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 100 --timeout-ms 15000 2>/dev/null \
  | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('device_type') == 'cctv':
            mfr = d.get('manufacturer','')
            hostname = d.get('hostname','')
            sn = d.get('serial_number','')
            if mfr.lower() in ('epson','hp','canon','brother','xerox','lexmark') \
               or hostname == 'unknown' or sn in ('NO_SN','NO_IDENTIFIER',''):
                print(f"MASALAH: ip={d.get('ip')} hostname={hostname} "
                      f"sn={sn} manufacturer={mfr} model={d.get('model')}")
    except: pass
"
```

### 1d. Cek tabel PostgreSQL yang sudah ada
```bash
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
  SELECT table_name FROM information_schema.tables
  WHERE table_schema = 'public' ORDER BY table_name;
"
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
  SELECT column_name, data_type FROM information_schema.columns
  WHERE table_name = 'dcim_events' ORDER BY ordinal_position;
" 2>/dev/null || echo "Table dcim_events does not exist yet"
```

---

## STEP 2: Fix CCTV — Blokir Data Non-CCTV SEBELUM Buat Tabel

Sebelum membuat tabel, perbaiki enrichment API agar tidak melakukan hostname fallback
untuk device dengan serial_number = NO_SN atau hostname = unknown.

Update `/home/infra/dcim_metrics_project/phase2/enrichment_api.py`:

```python
INVALID_IDENTIFIERS = {"NO_SN", "NO_IDENTIFIER", "unknown", "", None}

@app.get("/enrich/{serial_number}")
async def enrich_asset(serial_number: str, hostname: str = None):
    # Blokir lookup jika identifier tidak valid
    if serial_number in INVALID_IDENTIFIERS:
        if hostname in INVALID_IDENTIFIERS or hostname is None:
            # Tidak ada identifier yang bisa dipakai — kembalikan kosong
            return {
                "enrichment_status": "NO_IDENTIFIER",
                "enrichment_match_method": "none",
                "enrichment_match_confidence": "none",
                "site": None, "rack_name": None,
                "manufacturer": None, "model": None
            }
        # Jangan lakukan hostname fallback untuk device_type=cctv
        # karena berisiko dapat data device lain (printer, dll)
        return {
            "enrichment_status": "NO_IDENTIFIER",
            "enrichment_match_method": "blocked",
            "enrichment_match_confidence": "none",
            "note": "hostname fallback disabled for unknown devices"
        }
    
    # Normal flow: lookup via serial_number
    cached = redis_client.get(f"asset:{serial_number}")
    if cached:
        return json.loads(cached)
    
    # Fallback ke Ralph hanya jika serial_number valid
    return lookup_single_asset(serial_number)
```

Konfirmasi perubahan ini sebelum lanjut ke pembuatan tabel.

---

## STEP 3: Buat Tabel PostgreSQL — Full Schema

```sql
-- Jalankan di: 192.168.101.73, database: dcim_sot
-- Jika tabel sudah ada dengan nama berbeda, gunakan ALTER TABLE

CREATE TABLE IF NOT EXISTS dcim_events (

  -- ================================================================
  -- IDENTITAS & TRACEABILITY
  -- ================================================================
  event_id                      VARCHAR(36) PRIMARY KEY,
  event_time                    TIMESTAMPTZ,
  timestamp_epoch               BIGINT,
  source_topic                  VARCHAR(255),
  measurement                   VARCHAR(100),
  inserted_at                   TIMESTAMPTZ DEFAULT NOW(),

  -- ================================================================
  -- IDENTITAS PERANGKAT
  -- ================================================================
  device_type                   VARCHAR(50),
  hostname                      VARCHAR(255),
  ip                            INET,
  serial_number                 VARCHAR(100),

  -- ================================================================
  -- CDM METRIC FIELDS
  -- ================================================================
  metric_name                   VARCHAR(100),
  metric_value                  NUMERIC,
  metric_unit                   VARCHAR(50),
  severity                      VARCHAR(20),

  -- ================================================================
  -- CMDB ENRICHMENT CONTEXT
  -- ================================================================
  site                          VARCHAR(255),
  rack_name                     VARCHAR(255),
  rack_position                 SMALLINT,
  room_name                     VARCHAR(255),
  manufacturer                  VARCHAR(255),
  model                         VARCHAR(255),
  asset_status                  VARCHAR(50),
  environment                   VARCHAR(50),
  business_unit                 VARCHAR(255),
  enrichment_status             VARCHAR(30),
  enrichment_match_method       VARCHAR(50),
  enrichment_match_confidence   VARCHAR(20),
  last_modified_cmdb            TIMESTAMPTZ,
  cached_at                     TIMESTAMPTZ,

  -- ================================================================
  -- UPS-SPECIFIC (nullable untuk non-UPS)
  -- Sumber: raw_fields dari measurement ups_apc
  -- ================================================================
  ups_battery_capacity          SMALLINT,        -- upsBatteryCapacity (%)
  ups_battery_runtime           INT,             -- upsBatteryRuntime (detik)
  ups_battery_temp              NUMERIC(5,2),    -- upsBatteryTemp (°C)
  ups_battery_status            SMALLINT,        -- upsBatteryStatus (1=normal,2=low,3=depleted)
  ups_input_voltage             NUMERIC(6,2),    -- upsInputVoltage (V)
  ups_output_voltage            NUMERIC(6,2),    -- upsOutputVoltage (V)
  ups_output_load               SMALLINT,        -- upsOutputLoad (%)
  ups_output_frequency          NUMERIC(6,2),    -- upsOutputFrequency (x0.1 Hz)
  ups_output_status             SMALLINT,        -- upsOutputStatus (1=other,2=online,3=onBattery)
  ups_seconds_on_battery        INT,             -- upsSecondsOnBattery
  ups_firmware                  VARCHAR(100),    -- upsFirmware
  ups_model_snmp                VARCHAR(100),    -- upsModel (dari SNMP, beda dari CMDB model)
  ups_serial_snmp               VARCHAR(100),    -- upsSerial (dari SNMP)
  ups_sys_descr                 VARCHAR(255),    -- sysDescr
  ups_sys_uptime                BIGINT,          -- sysUpTime (timeticks)

  -- ================================================================
  -- NAS-SPECIFIC (nullable untuk non-NAS)
  -- Sumber: raw_fields dari measurement dcim_nas / nas_snmp
  -- ================================================================
  nas_disk_id                   VARCHAR(50),     -- diskID (e.g. "Disk 3")
  nas_disk_model                VARCHAR(255),    -- diskModel
  nas_disk_status               SMALLINT,        -- diskStatus (1=normal,2=warning,3=critical)
  nas_disk_temp                 NUMERIC(5,2),    -- diskTemp (°C)
  nas_system_temp               NUMERIC(5,2),    -- system_temp (°C)
  nas_sys_descr                 VARCHAR(255),    -- sysDescr
  nas_sys_uptime                BIGINT,          -- sysUpTime
  nas_storage_size              BIGINT,          -- storageSize
  nas_storage_used              BIGINT,          -- storageUsed
  nas_storage_type              VARCHAR(50),     -- storage_type (RAM/HDD/SSD)
  nas_storage_descr             VARCHAR(255),    -- storageDescr

  -- ================================================================
  -- NETWORK SWITCH-SPECIFIC (nullable untuk non-network)
  -- Sumber: raw_fields dari measurement interface / dcim_network_storage
  -- ================================================================
  net_if_index                  VARCHAR(20),     -- ifIndex / hrStorageIndex
  net_if_name                   VARCHAR(100),    -- if_name
  net_if_descr                  VARCHAR(255),    -- ifDescr / storageDescr
  net_if_oper_status            SMALLINT,        -- ifOperStatus (1=up,2=down)
  net_if_admin_status           SMALLINT,        -- ifAdminStatus (1=up,2=down)
  net_if_speed                  BIGINT,          -- ifSpeed (bps)
  net_if_mtu                    INT,             -- ifMtu
  net_if_type                   SMALLINT,        -- ifType
  net_if_in_octets              BIGINT,          -- if_in_octets (64-bit counter)
  net_if_out_octets             BIGINT,          -- if_out_octets (64-bit counter)
  net_if_in_octets_32           BIGINT,          -- ifInOctets (32-bit, bisa wrap)
  net_if_out_octets_32          BIGINT,          -- ifOutOctets (32-bit, bisa wrap)
  net_if_in_ucast_pkts          BIGINT,          -- ifInUcastPkts
  net_if_out_ucast_pkts         BIGINT,          -- ifOutUcastPkts
  net_if_in_nucast_pkts         BIGINT,          -- ifInNUcastPkts
  net_if_out_nucast_pkts        BIGINT,          -- ifOutNUcastPkts
  net_if_in_errors              INT,             -- ifInErrors
  net_if_out_errors             INT,             -- ifOutErrors
  net_if_in_discards            INT,             -- ifInDiscards
  net_if_out_discards           INT,             -- ifOutDiscards
  net_if_in_unknown_protos      INT,             -- ifInUnknownProtos
  net_if_phys_address           VARCHAR(17),     -- ifPhysAddress (MAC)
  net_if_last_change            BIGINT,          -- ifLastChange
  net_if_out_qlen               INT,             -- ifOutQLen
  net_storage_size              BIGINT,          -- storageSize (network device memory)
  net_storage_used              BIGINT,          -- storageUsed
  net_storage_type              VARCHAR(50),     -- storage_type

  -- ================================================================
  -- SERVER-SPECIFIC (nullable untuk non-server)
  -- Sumber: raw_fields dari measurement server_redfish
  -- CATATAN: Kolom ini berdasarkan perkiraan Redfish schema.
  -- Update setelah Step 1a menemukan sample data server aktual.
  -- ================================================================
  srv_sensor_name               VARCHAR(100),    -- nama sensor Redfish
  srv_reading_celsius           NUMERIC(6,2),    -- reading_celsius
  srv_upper_threshold_critical  NUMERIC(6,2),    -- upper_threshold_critical
  srv_upper_threshold_fatal     NUMERIC(6,2),    -- upper_threshold_fatal
  srv_power_watts               NUMERIC(8,2),    -- power_watts
  srv_health                    VARCHAR(50),     -- health status dari Redfish
  srv_state                     VARCHAR(50),     -- state dari Redfish
  srv_firmware                  VARCHAR(100),    -- firmware version
  srv_cpu_load                  NUMERIC(5,2),    -- CPU load %
  srv_memory_used_mb            BIGINT,          -- memory used MB
  srv_memory_total_mb           BIGINT,          -- memory total MB

  -- ================================================================
  -- CCTV-SPECIFIC (nullable untuk non-CCTV)
  -- Sumber: raw_fields dari measurement cctv_metrics
  -- ================================================================
  cctv_status_online            SMALLINT,        -- status_online (0=offline,1=online)
  cctv_status_text              VARCHAR(50),     -- status_text ("Online"/"Offline")
  cctv_channel_count            SMALLINT,        -- channelCount
  cctv_recording_status         VARCHAR(50),     -- recordingStatus
  cctv_device_name              VARCHAR(255),    -- deviceName dari ISAPI

  -- ================================================================
  -- FULL RAW DATA — tidak ada data yang hilang
  -- ================================================================
  raw_fields                    JSONB,           -- semua field mentah dari device
  raw_tags                      JSONB            -- semua tag asli dari Telegraf
);

-- ================================================================
-- INDEXES
-- ================================================================
CREATE INDEX IF NOT EXISTS idx_dcim_event_time
  ON dcim_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_dcim_device_type
  ON dcim_events(device_type);
CREATE INDEX IF NOT EXISTS idx_dcim_serial
  ON dcim_events(serial_number);
CREATE INDEX IF NOT EXISTS idx_dcim_hostname
  ON dcim_events(hostname);
CREATE INDEX IF NOT EXISTS idx_dcim_site
  ON dcim_events(site);
CREATE INDEX IF NOT EXISTS idx_dcim_severity
  ON dcim_events(severity);
CREATE INDEX IF NOT EXISTS idx_dcim_enrichment_status
  ON dcim_events(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_dcim_raw_fields_gin
  ON dcim_events USING GIN(raw_fields);
CREATE INDEX IF NOT EXISTS idx_dcim_site_device_time
  ON dcim_events(site, device_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_dcim_source_topic
  ON dcim_events(source_topic);
```

> ⚠️ Jika tabel sudah ada: gunakan `ALTER TABLE dcim_events ADD COLUMN IF NOT EXISTS`
> untuk setiap kolom baru. **Jangan DROP tabel yang sudah berisi data.**

---

## STEP 4: Buat Consumer Script

Buat `/home/infra/dcim_metrics_project/phase2/dcim_postgres_consumer.py`

Script ini harus:
1. Subscribe ke `dcim.enriched.events`
2. Map semua top-level field ke kolom shared
3. Map semua `raw_fields` ke kolom device-specific sesuai tabel di bawah
4. Simpan `raw_fields` dan `raw_tags` sebagai JSONB (fallback, tidak pernah hilang)
5. Gunakan `INSERT ... ON CONFLICT (event_id) DO UPDATE` (idempotent)
6. Log key `raw_fields` yang belum ada di mapping (untuk deteksi field baru)

**Mapping raw_fields → kolom PostgreSQL yang harus diimplementasi:**

```python
RAW_FIELD_MAP = {
    # UPS
    "upsBatteryCapacity":   ("ups_battery_capacity",   int),
    "upsBatteryRuntime":    ("ups_battery_runtime",    int),
    "upsBatteryTemp":       ("ups_battery_temp",       float),
    "upsBatteryStatus":     ("ups_battery_status",     int),
    "upsInputVoltage":      ("ups_input_voltage",      float),
    "upsOutputVoltage":     ("ups_output_voltage",     float),
    "upsOutputLoad":        ("ups_output_load",        int),
    "upsOutputFrequency":   ("ups_output_frequency",   float),
    "upsOutputStatus":      ("ups_output_status",      int),
    "upsSecondsOnBattery":  ("ups_seconds_on_battery", int),
    "upsFirmware":          ("ups_firmware",           str),
    "upsModel":             ("ups_model_snmp",         str),
    "upsSerial":            ("ups_serial_snmp",        str),
    "sysUpTime":            ("ups_sys_uptime",         int),  # shared UPS/NAS

    # NAS
    "diskID":               ("nas_disk_id",            str),
    "diskModel":            ("nas_disk_model",         str),
    "diskStatus":           ("nas_disk_status",        int),
    "diskTemp":             ("nas_disk_temp",          float),
    "system_temp":          ("nas_system_temp",        float),
    "storageSize":          ("nas_storage_size",       int),
    "storageUsed":          ("nas_storage_used",       int),
    "storage_type":         ("nas_storage_type",       str),
    "storageDescr":         ("nas_storage_descr",      str),

    # Network Switch — interface
    "if_name":              ("net_if_name",            str),
    "ifDescr":              ("net_if_descr",           str),
    "ifOperStatus":         ("net_if_oper_status",     int),
    "if_oper_status":       ("net_if_oper_status",     int),  # alias
    "ifAdminStatus":        ("net_if_admin_status",    int),
    "ifSpeed":              ("net_if_speed",           int),
    "ifMtu":                ("net_if_mtu",             int),
    "ifType":               ("net_if_type",            int),
    "if_in_octets":         ("net_if_in_octets",       int),
    "if_out_octets":        ("net_if_out_octets",      int),
    "ifInOctets":           ("net_if_in_octets_32",    int),
    "ifOutOctets":          ("net_if_out_octets_32",   int),
    "ifInUcastPkts":        ("net_if_in_ucast_pkts",   int),
    "ifOutUcastPkts":       ("net_if_out_ucast_pkts",  int),
    "ifInNUcastPkts":       ("net_if_in_nucast_pkts",  int),
    "ifOutNUcastPkts":      ("net_if_out_nucast_pkts", int),
    "ifInErrors":           ("net_if_in_errors",       int),
    "ifOutErrors":          ("net_if_out_errors",      int),
    "ifInDiscards":         ("net_if_in_discards",     int),
    "ifOutDiscards":        ("net_if_out_discards",    int),
    "ifInUnknownProtos":    ("net_if_in_unknown_protos",int),
    "ifPhysAddress":        ("net_if_phys_address",    str),
    "ifLastChange":         ("net_if_last_change",     int),
    "ifOutQLen":            ("net_if_out_qlen",        int),

    # Server Redfish — UPDATE setelah Step 1a menemukan sample aktual
    "reading_celsius":           ("srv_reading_celsius",          float),
    "upper_threshold_critical":  ("srv_upper_threshold_critical", float),
    "upper_threshold_fatal":     ("srv_upper_threshold_fatal",    float),
    "power_watts":               ("srv_power_watts",              float),

    # CCTV
    "status_online":        ("cctv_status_online",     int),
    "status_text":          ("cctv_status_text",       str),
    "channelCount":         ("cctv_channel_count",     int),
    "recordingStatus":      ("cctv_recording_status",  str),
    "deviceName":           ("cctv_device_name",       str),
}

# raw_tags yang perlu dipetakan ke kolom spesifik per device_type
RAW_TAGS_MAP = {
    "firmware": {
        "server_redfish": "srv_firmware",
        "server":         "srv_firmware",
    },
    "health": {
        "server_redfish": "srv_health",
        "server":         "srv_health",
        "cctv":           "cctv_health",  # jika ada
    },
    "state": {
        "server_redfish": "srv_state",
        "server":         "srv_state",
    },
    "hrStorageIndex": {
        "network_switch": "net_if_index",
        "mikrotik":       "net_if_index",
    },
    "ifIndex": {
        "network_switch": "net_if_index",
        "mikrotik":       "net_if_index",
    },
    "sysDescr": {
        "ups": "ups_sys_descr",
        "nas": "nas_sys_descr",
    }
}
```

Tampilkan script lengkap sebelum menulis ke disk. Minta konfirmasi sebelum eksekusi.

---

## STEP 5: Elasticsearch Index Template

```bash
curl -k -u elastic:'<password>' -X PUT \
  "https://10.70.0.56:9200/_index_template/dcim-enriched-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["dcim-enriched-*"],
    "priority": 100,
    "template": {
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "10s"
      },
      "mappings": {
        "dynamic": true,
        "properties": {
          "event_id":                    {"type": "keyword"},
          "event_time":                  {"type": "date"},
          "timestamp":                   {"type": "date", "format": "epoch_second"},
          "source_topic":                {"type": "keyword"},
          "measurement":                 {"type": "keyword"},
          "device_type":                 {"type": "keyword"},
          "hostname":                    {"type": "keyword"},
          "ip":                          {"type": "ip"},
          "serial_number":               {"type": "keyword"},
          "metric_name":                 {"type": "keyword"},
          "metric_value":                {"type": "float"},
          "metric_unit":                 {"type": "keyword"},
          "severity":                    {"type": "keyword"},
          "site":                        {"type": "keyword"},
          "rack_name":                   {"type": "keyword"},
          "rack_position":               {"type": "integer"},
          "room_name":                   {"type": "keyword"},
          "manufacturer":                {"type": "keyword"},
          "model":                       {"type": "keyword"},
          "asset_status":                {"type": "keyword"},
          "environment":                 {"type": "keyword"},
          "business_unit":               {"type": "keyword"},
          "enrichment_status":           {"type": "keyword"},
          "enrichment_match_method":     {"type": "keyword"},
          "enrichment_match_confidence": {"type": "keyword"},
          "last_modified_cmdb":          {"type": "date"},
          "cached_at":                   {"type": "date"},
          "raw_fields":                  {"type": "object", "dynamic": true},
          "raw_tags":                    {"type": "object", "dynamic": true},
          "ups_battery_capacity":        {"type": "short"},
          "ups_battery_temp":            {"type": "float"},
          "ups_battery_runtime":         {"type": "integer"},
          "ups_battery_status":          {"type": "short"},
          "ups_input_voltage":           {"type": "float"},
          "ups_output_voltage":          {"type": "float"},
          "ups_output_load":             {"type": "short"},
          "nas_disk_temp":               {"type": "float"},
          "nas_disk_status":             {"type": "short"},
          "nas_system_temp":             {"type": "float"},
          "net_if_oper_status":          {"type": "short"},
          "net_if_admin_status":         {"type": "short"},
          "net_if_in_octets":            {"type": "long"},
          "net_if_out_octets":           {"type": "long"},
          "net_if_speed":                {"type": "long"},
          "net_if_in_errors":            {"type": "integer"},
          "net_if_out_errors":           {"type": "integer"},
          "srv_reading_celsius":         {"type": "float"},
          "srv_power_watts":             {"type": "float"},
          "srv_upper_threshold_critical":{"type": "float"},
          "srv_upper_threshold_fatal":   {"type": "float"},
          "cctv_status_online":          {"type": "short"},
          "cctv_channel_count":          {"type": "short"}
        }
      }
    }
  }'
```

---

## STEP 6: Validasi End-to-End

### 6a. Validasi PostgreSQL per device type
```bash
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT
  device_type,
  COUNT(*) as total_events,
  COUNT(site) as has_site,
  COUNT(rack_name) as has_rack,
  COUNT(enrichment_status) as has_enrichment,
  MAX(event_time) as latest
FROM dcim_events
GROUP BY device_type ORDER BY total_events DESC;
"

# Cek kolom UPS terisi
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, serial_number,
  ups_battery_capacity, ups_battery_temp,
  ups_input_voltage, ups_output_voltage, ups_output_load,
  site, rack_name, business_unit, enrichment_status
FROM dcim_events WHERE device_type='ups'
ORDER BY event_time DESC LIMIT 3;
"

# Cek kolom network terisi
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, net_if_name, net_if_oper_status,
  net_if_in_octets, net_if_out_octets, site
FROM dcim_events WHERE device_type='network_switch'
ORDER BY event_time DESC LIMIT 3;
"

# Pastikan CCTV tidak ada manufacturer Epson/printer
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, ip, serial_number, manufacturer, model, enrichment_status
FROM dcim_events WHERE device_type='cctv'
ORDER BY event_time DESC LIMIT 10;
"

# Cek raw_fields key yang belum dipetakan ke kolom
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT device_type, jsonb_object_keys(raw_fields) as field_key, COUNT(*)
FROM dcim_events
GROUP BY device_type, field_key
ORDER BY device_type, count DESC;
"
```

### 6b. Validasi Elasticsearch field types
```bash
curl -k -u elastic:'<password>' \
  "https://10.70.0.56:9200/dcim-enriched-*/_mapping" \
  | python3 -c "
import sys, json
m = json.load(sys.stdin)
for idx in list(m.keys())[:1]:
    props = m[idx]['mappings'].get('properties', {})
    check = {
      'event_time': 'date', 'timestamp': 'date',
      'device_type': 'keyword', 'metric_value': 'float',
      'ups_battery_capacity': 'short',
      'net_if_in_octets': 'long',
      'srv_reading_celsius': 'float'
    }
    for field, expected in check.items():
        actual = props.get(field, {}).get('type', 'MISSING')
        status = '✅' if actual == expected else '❌'
        print(f'{status} {field}: expected={expected}, actual={actual}')
"
```

**PASS condition:**
- Semua device type ada di tabel PostgreSQL
- Kolom device-specific (ups_*, nas_*, net_*, srv_*, cctv_*) non-null untuk device yang sesuai
- CCTV tidak ada manufacturer printer/non-CCTV
- Server ditemukan dan kolom srv_* terisi
- Elasticsearch: timestamp bertipe `date`, bukan `long`

---

## CONSTRAINTS
- Baca `dcim_sql_consumer.py` yang sudah ada sebelum membuat script baru
- Jika tabel `device_metrics` sudah ada dan berisi data, jangan dihapus —
  buat tabel baru `dcim_events` secara terpisah
- Kolom server (srv_*) **hanya dibuat setelah Step 1a menemukan sample aktual**
  dan field names dikonfirmasi dari data nyata
- Jangan hapus data CCTV yang sudah ada — hanya blokir data baru yang salah
- Tampilkan script lengkap dan minta konfirmasi sebelum:
  - Menulis file Python ke disk
  - Menjalankan CREATE TABLE
  - Me-restart service apapun
- Jika ada unmapped raw_fields key setelah validasi, tambahkan ke RAW_FIELD_MAP
  dan ALTER TABLE untuk tambah kolom, lalu restart consumer
```
