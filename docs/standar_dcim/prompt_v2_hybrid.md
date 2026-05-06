# Agent Prompt — Database Storage (Rekomendasi: Hybrid Schema)
> **Versi**: B — Hybrid Schema (Kolom shared + kolom query-critical + JSONB untuk sisanya)
> **Target DB**: PostgreSQL + Elasticsearch
> **Source**: `dcim.enriched.events`
> **Generated**: April 2026

---

## Filosofi Desain Versi Ini

Versi ini menggunakan **hybrid approach** — tidak semua raw_fields dijadikan kolom dedicated.
Yang dijadikan kolom adalah field yang benar-benar sering di-query, di-filter, atau di-alert.
Sisanya tetap tersimpan lengkap di `raw_fields JSONB` — tidak ada data yang hilang,
tapi tabel tidak punya ratusan kolom sparse yang mayoritas NULL.

```
Kolom dedicated  → query cepat, index optimal, AI-ready
JSONB fallback   → tidak ada data hilang, bisa di-query dengan ->>'field'
```

Ini sesuai dengan arah AI/ML readiness: kolom flat untuk feature engineering,
JSONB untuk full-fidelity replay dan audit.

---

## Data Aktual per Device Type

### Device 1 — Network Switch (MikroTik)
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
    "ifOutOctets": 3766575171, "if_name": "combo3",
    "if_in_octets": 19595013676244,
    "if_out_octets": 33658671369801
  },
  "site": "Local Instance", "rack_name": "Rack Server 2",
  "rack_position": 40, "manufacturer": "MikroTik",
  "model": "CRS312-4C+8XG-RM", "asset_status": "in use",
  "environment": "Production",
  "business_unit": "IT Infrastructure Departement",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:46.174284",
  "cached_at": "2026-04-28T03:25:10.968253"
}
```

### Device 2 — UPS (APC)
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
    "upsBatteryCapacity": 100, "upsBatteryRuntime": 506,
    "upsBatteryTemp": 23, "upsBatteryStatus": 2,
    "upsInputVoltage": 228, "upsOutputVoltage": 231,
    "upsOutputLoad": 2, "upsSecondsOnBattery": 0
  },
  "site": "Local Instance", "rack_name": "Ruang server",
  "rack_position": 1, "manufacturer": "APC",
  "model": "APC Easy UPS 3S 30kVA 30kW",
  "asset_status": "in use", "environment": "Production",
  "business_unit": "Facility Management Department",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:54.712660",
  "cached_at": "2026-04-28T03:25:10.949598"
}
```

### Device 3 — NAS (Synology)
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
    "diskStatus": 1, "diskTemp": 30,
    "diskID": "Disk 3", "system_temp": 33
  },
  "site": "Local Instance", "rack_name": "Rack Server 2",
  "rack_position": 1, "manufacturer": "Synology",
  "model": "DS220+", "asset_status": "in use",
  "environment": "Production",
  "business_unit": "IT Infrastructure Departement",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:54.341710",
  "cached_at": "2026-04-28T03:25:10.949088"
}
```

### Device 4 — CCTV (Hikvision) — BUG AKTIF
```json
{
  "event_id": "645a5cce-40e8-4442-8465-923e7a21f9e0",
  "event_time": "2026-04-27T20:43:00+00:00",
  "source_topic": "dcim.raw.device.isapi",
  "measurement": "cctv_metrics",
  "device_type": "cctv",
  "hostname": "unknown", "ip": "192.168.1.5",
  "serial_number": "NO_SN",
  "metric_name": "general_metric",
  "metric_value": null, "metric_unit": null,
  "raw_fields": {"status_online": 0, "status_text": "Offline"},
  "manufacturer": "Epson",
  "model": "WorkForce WF-7710",
  "enrichment_status": "NO_IDENTIFIER",
  "enrichment_match_method": "hostname_fallback",
  "enrichment_match_confidence": "low"
}
```

> ⚠️ **Bug**: manufacturer = Epson (printer) karena hostname fallback dengan "unknown".
> Harus diblokir di enrichment API sebelum data masuk ke database.

### Device 5 — Server — BELUM ADA SAMPLE
> ⚠️ Agent harus ambil sample dari Kafka di Step 1 sebelum membuat kolom server.

---

## Keputusan Kolom: Mana yang Dedicated, Mana yang JSONB

Prinsip: **kolom dedicated hanya untuk field yang masuk ke salah satu kategori ini:**

| Kategori | Contoh |
|---|---|
| Field yang sering jadi filter WHERE | `device_type`, `severity`, `enrichment_status` |
| Field yang sering di-aggregate (SUM/AVG/MAX) | `metric_value`, `ups_battery_capacity`, `disk_temp` |
| Field untuk alerting threshold | `ups_battery_capacity < 20`, `disk_temp > 45` |
| Field untuk AI feature engineering | semua metric numerik per device |
| Field untuk JOIN atau GROUP BY | `serial_number`, `site`, `rack_name` |

Field yang **cukup di JSONB** (query via `raw_fields->>'field'`):
- Counter 64-bit yang jarang di-aggregate (ifInUcastPkts, ifLastChange, dll)
- String descriptif (ifDescr, sysDescr, storageDescr)
- Field yang hanya muncul di 1-2 device dan tidak pernah di-alert

---

## STEP 1: Audit & Discovery

### 1a. Ambil sample server dari Kafka — WAJIB
```bash
# Cari topic server
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --list --bootstrap-server localhost:9092 \
  | grep -iE "server|redfish|ipmi|lenovo|dell"

# Sample enriched events dan filter device_type server
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 100 --timeout-ms 20000 2>/dev/null \
  | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        dt = d.get('device_type','')
        if any(x in dt.lower() for x in ['server','redfish','lenovo','dell','hp']):
            print(json.dumps(d, indent=2))
            break
    except: pass
" 
```

**STOP jika tidak ada. Laporkan ke operator dan skip kolom srv_* sampai ada data.**

### 1b. Identifikasi semua device_type aktif dan raw_fields mereka
```bash
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 300 --timeout-ms 30000 2>/dev/null \
  | python3 -c "
import sys, json
seen = {}
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        dt = d.get('device_type','unknown')
        if dt not in seen:
            rf = d.get('raw_fields', {})
            seen[dt] = {
                'measurement': d.get('measurement'),
                'numeric_fields': {k: type(v).__name__
                  for k,v in rf.items() if isinstance(v,(int,float))},
                'string_fields': [k for k,v in rf.items()
                  if isinstance(v,str)],
                'enrichment_status': d.get('enrichment_status'),
                'sample_hostname': d.get('hostname')
            }
    except: pass
import json; print(json.dumps(seen, indent=2))
"
```

Laporkan hasil sebelum lanjut ke Step 2.

### 1c. Deteksi CCTV yang masukkan data non-CCTV
```bash
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 100 --timeout-ms 15000 2>/dev/null \
  | python3 -c "
import sys, json
NON_CCTV_BRANDS = {'epson','hp','canon','brother','xerox','lexmark','samsung printer'}
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('device_type') == 'cctv':
            mfr = (d.get('manufacturer') or '').lower()
            sn = d.get('serial_number','')
            hn = d.get('hostname','')
            is_bad = (mfr in NON_CCTV_BRANDS or
                      sn in ('NO_SN','NO_IDENTIFIER') or
                      hn == 'unknown')
            if is_bad:
                print(f'BUG CCTV: ip={d.get(\"ip\")} '
                      f'hostname={hn} sn={sn} '
                      f'manufacturer={d.get(\"manufacturer\")} '
                      f'model={d.get(\"model\")}')
    except: pass
"
```

---

## STEP 2: Fix CCTV Bug — Blokir Hostname Fallback untuk Unknown Device

Update `/home/infra/dcim_metrics_project/phase2/enrichment_api.py`:

```python
INVALID_IDENTIFIERS = frozenset({"NO_SN", "NO_IDENTIFIER", "unknown", "", None})

@app.get("/enrich/{serial_number}")
async def enrich_asset(serial_number: str):
    # Jika identifier tidak valid — kembalikan status tanpa lookup
    # Ini mencegah hostname "unknown" mendapat data device lain (printer, dll)
    if serial_number in INVALID_IDENTIFIERS:
        return {
            "enrichment_status": "NO_IDENTIFIER",
            "enrichment_match_method": "none",
            "enrichment_match_confidence": "none",
            "site": None, "rack_name": None,
            "manufacturer": None, "model": None,
            "asset_status": None, "business_unit": None
        }

    # Fast path: Redis cache
    cached = redis_client.get(f"asset:{serial_number}")
    if cached:
        return json.loads(cached)

    # Fallback: direct Ralph lookup (hanya untuk SN yang valid)
    return lookup_single_asset(serial_number)
```

Restart enrichment API setelah update:
```bash
systemctl restart dcim-enrichment-api.service
sleep 5
systemctl status dcim-enrichment-api.service --no-pager | head -10

# Test: pastikan NO_SN tidak dapat data enrichment
curl -s http://127.0.0.1:8000/enrich/NO_SN | python3 -m json.tool
# Expected: enrichment_status = "NO_IDENTIFIER", manufacturer = null
```

---

## STEP 3: Buat Tabel PostgreSQL — Hybrid Schema

```sql
-- Jalankan di: 192.168.101.73, database: dcim_sot

CREATE TABLE IF NOT EXISTS dcim_events (

  -- ============================================================
  -- IDENTITAS & TRACEABILITY — semua jadi kolom, selalu dibutuhkan
  -- ============================================================
  event_id                      VARCHAR(36) PRIMARY KEY,
  event_time                    TIMESTAMPTZ NOT NULL,
  timestamp_epoch               BIGINT,
  source_topic                  VARCHAR(255),
  measurement                   VARCHAR(100),
  inserted_at                   TIMESTAMPTZ DEFAULT NOW(),

  -- ============================================================
  -- IDENTITAS PERANGKAT — kolom dedicated, sering di-filter
  -- ============================================================
  device_type                   VARCHAR(50),
  hostname                      VARCHAR(255),
  ip                            INET,
  serial_number                 VARCHAR(100),

  -- ============================================================
  -- CDM METRIC — kolom dedicated, dipakai alerting & AI features
  -- ============================================================
  metric_name                   VARCHAR(100),
  metric_value                  NUMERIC,          -- nilai utama (battery%, temp, dll)
  metric_unit                   VARCHAR(50),
  severity                      VARCHAR(20),

  -- ============================================================
  -- CMDB CONTEXT — kolom dedicated, sering GROUP BY & JOIN
  -- ============================================================
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

  -- ============================================================
  -- UPS — hanya metric yang dipakai alerting & monitoring
  -- Sisanya ada di raw_fields JSONB
  -- ============================================================
  ups_battery_capacity          SMALLINT,     -- % → alert jika < 20
  ups_battery_runtime_sec       INT,          -- detik → alert jika < 300
  ups_battery_temp              NUMERIC(5,2), -- °C → alert jika > 40
  ups_battery_status            SMALLINT,     -- 1=normal,2=low,3=depleted
  ups_input_voltage             NUMERIC(6,2), -- V → deteksi voltage sag
  ups_output_voltage            NUMERIC(6,2), -- V
  ups_output_load               SMALLINT,     -- % → alert jika > 80
  ups_seconds_on_battery        INT,          -- > 0 berarti sedang on battery

  -- ============================================================
  -- NAS — metric utama untuk monitoring storage & disk health
  -- ============================================================
  nas_disk_id                   VARCHAR(50),  -- "Disk 3" → identifikasi disk
  nas_disk_status               SMALLINT,     -- 1=normal,2=warning,3=critical
  nas_disk_temp                 NUMERIC(5,2), -- °C → alert jika > 50
  nas_system_temp               NUMERIC(5,2), -- °C suhu chassis NAS

  -- ============================================================
  -- NETWORK SWITCH — metric operasional & traffic utama
  -- Counter detail (per-packet) tetap di raw_fields JSONB
  -- ============================================================
  net_if_name                   VARCHAR(100), -- nama interface, sering di-filter
  net_if_oper_status            SMALLINT,     -- 1=up,2=down → alert jika down
  net_if_admin_status           SMALLINT,     -- 1=up,2=down
  net_if_in_octets              BIGINT,       -- 64-bit counter, bandwidth calc
  net_if_out_octets             BIGINT,       -- 64-bit counter
  net_if_in_errors              INT,          -- error counter → alert jika naik
  net_if_out_errors             INT,
  net_if_speed                  BIGINT,       -- kapasitas link (bps)

  -- ============================================================
  -- SERVER — diisi setelah Step 1a menemukan sample aktual
  -- Kolom ini placeholder — sesuaikan dengan field nyata dari Redfish
  -- ============================================================
  srv_reading_celsius           NUMERIC(6,2), -- suhu sensor → alert jika > critical
  srv_upper_threshold_critical  NUMERIC(6,2), -- threshold untuk evaluasi severity
  srv_power_watts               NUMERIC(8,2), -- konsumsi daya server
  srv_health                    VARCHAR(50),  -- OK/Warning/Critical dari Redfish
  srv_state                     VARCHAR(50),  -- Enabled/Disabled

  -- ============================================================
  -- CCTV — status operasional kamera
  -- ============================================================
  cctv_status_online            SMALLINT,     -- 0=offline,1=online → alert jika 0
  cctv_status_text              VARCHAR(50),  -- "Online"/"Offline"

  -- ============================================================
  -- JSONB FALLBACK — semua raw_fields & raw_tags tersimpan lengkap
  -- Tidak ada data yang hilang. Bisa di-query: raw_fields->>'fieldName'
  -- ============================================================
  raw_fields                    JSONB NOT NULL,
  raw_tags                      JSONB
);

-- ============================================================
-- INDEXES — fokus pada query pattern yang nyata
-- ============================================================

-- Time-based queries (paling umum)
CREATE INDEX IF NOT EXISTS idx_dcim_event_time
  ON dcim_events(event_time DESC);

-- Dashboard filters
CREATE INDEX IF NOT EXISTS idx_dcim_device_type
  ON dcim_events(device_type);
CREATE INDEX IF NOT EXISTS idx_dcim_site_device_time
  ON dcim_events(site, device_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_dcim_enrichment_status
  ON dcim_events(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_dcim_severity
  ON dcim_events(severity);

-- Asset lookup
CREATE INDEX IF NOT EXISTS idx_dcim_serial
  ON dcim_events(serial_number);
CREATE INDEX IF NOT EXISTS idx_dcim_hostname
  ON dcim_events(hostname);

-- Alert queries
CREATE INDEX IF NOT EXISTS idx_dcim_ups_battery
  ON dcim_events(ups_battery_capacity)
  WHERE device_type = 'ups';
CREATE INDEX IF NOT EXISTS idx_dcim_net_if_status
  ON dcim_events(net_if_oper_status)
  WHERE device_type = 'network_switch';

-- JSONB queries untuk field yang belum punya kolom dedicated
CREATE INDEX IF NOT EXISTS idx_dcim_raw_fields_gin
  ON dcim_events USING GIN(raw_fields);
```

> ⚠️ Jika tabel sudah ada: gunakan `ALTER TABLE dcim_events ADD COLUMN IF NOT EXISTS`
> Jangan DROP tabel yang berisi data.

---

## STEP 4: Consumer Script — Hybrid Mapper

Buat `/home/infra/dcim_metrics_project/phase2/dcim_postgres_consumer.py`

Script menggunakan dua layer mapping:
1. `COLUMN_MAP` — field yang punya kolom dedicated (selalu cepat di-query)
2. `raw_fields JSONB` — semua field tersimpan, termasuk yang tidak ada di COLUMN_MAP

```python
#!/usr/bin/env python3
"""
DCIM PostgreSQL Consumer — Hybrid Schema
Dedicated columns untuk metric penting + JSONB untuk semua raw_fields.
"""
import json, logging, os, uuid
from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import Json

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

def read_secret(name):
    try:
        with open(f"/run/secrets/dcim/{name}") as f: return f.read().strip()
    except FileNotFoundError:
        return os.getenv(name)

# ── Mapping raw_fields → kolom dedicated ─────────────────────────────────────
# Hanya field yang punya kolom di tabel. Sisanya otomatis masuk JSONB.
COLUMN_MAP = {
    # UPS
    "upsBatteryCapacity":  ("ups_battery_capacity",     int),
    "upsBatteryRuntime":   ("ups_battery_runtime_sec",  int),
    "upsBatteryTemp":      ("ups_battery_temp",         float),
    "upsBatteryStatus":    ("ups_battery_status",       int),
    "upsInputVoltage":     ("ups_input_voltage",        float),
    "upsOutputVoltage":    ("ups_output_voltage",       float),
    "upsOutputLoad":       ("ups_output_load",          int),
    "upsSecondsOnBattery": ("ups_seconds_on_battery",   int),

    # NAS
    "diskStatus":          ("nas_disk_status",          int),
    "diskTemp":            ("nas_disk_temp",            float),
    "system_temp":         ("nas_system_temp",          float),

    # Network Switch
    "if_name":             ("net_if_name",              str),
    "ifOperStatus":        ("net_if_oper_status",       int),
    "if_oper_status":      ("net_if_oper_status",       int),   # alias
    "ifAdminStatus":       ("net_if_admin_status",      int),
    "if_in_octets":        ("net_if_in_octets",         int),   # 64-bit
    "if_out_octets":       ("net_if_out_octets",        int),   # 64-bit
    "ifInErrors":          ("net_if_in_errors",         int),
    "ifOutErrors":         ("net_if_out_errors",        int),
    "ifSpeed":             ("net_if_speed",             int),

    # Server Redfish — UPDATE setelah Step 1a
    "reading_celsius":          ("srv_reading_celsius",          float),
    "upper_threshold_critical": ("srv_upper_threshold_critical", float),
    "power_watts":              ("srv_power_watts",              float),

    # CCTV
    "status_online":       ("cctv_status_online",       int),
    "status_text":         ("cctv_status_text",         str),
}

# raw_tags yang perlu di-promote ke kolom dedicated per device_type
TAGS_TO_COLUMNS = {
    "health": {"server": "srv_health", "server_redfish": "srv_health"},
    "state":  {"server": "srv_state",  "server_redfish": "srv_state"},
}

# NAS: disk_id ada di raw_tags
NAS_DISK_ID_TAG = "diskID"


def map_event(event: dict) -> dict:
    """Map enriched event ke row dictionary untuk INSERT."""
    dt = event.get("device_type", "unknown")
    rf = event.get("raw_fields", {})
    rt = event.get("raw_tags", {})

    # Shared fields — semua masuk kolom dedicated
    row = {
        "event_id":                   event.get("event_id") or str(uuid.uuid4()),
        "event_time":                 event.get("event_time"),
        "timestamp_epoch":            event.get("timestamp"),
        "source_topic":               event.get("source_topic"),
        "measurement":                event.get("measurement"),
        "device_type":                dt,
        "hostname":                   event.get("hostname"),
        "ip":                         event.get("ip"),
        "serial_number":              event.get("serial_number"),
        "metric_name":                event.get("metric_name"),
        "metric_value":               event.get("metric_value"),
        "metric_unit":                event.get("metric_unit"),
        "severity":                   event.get("severity"),
        "site":                       event.get("site"),
        "rack_name":                  event.get("rack_name"),
        "rack_position":              event.get("rack_position"),
        "room_name":                  event.get("room_name"),
        "manufacturer":               event.get("manufacturer"),
        "model":                      event.get("model"),
        "asset_status":               event.get("asset_status"),
        "environment":                event.get("environment"),
        "business_unit":              event.get("business_unit"),
        "enrichment_status":          event.get("enrichment_status"),
        "enrichment_match_method":    event.get("enrichment_match_method"),
        "enrichment_match_confidence":event.get("enrichment_match_confidence"),
        "last_modified_cmdb":         event.get("last_modified_cmdb"),
        "cached_at":                  event.get("cached_at"),
        "raw_fields":                 Json(rf),
        "raw_tags":                   Json(rt),
    }

    # Map raw_fields ke kolom dedicated
    unmapped = []
    for rf_key, rf_val in rf.items():
        if rf_key in COLUMN_MAP:
            col, cast = COLUMN_MAP[rf_key]
            # Jangan overwrite jika sudah ada nilai (alias handling)
            if col not in row or row.get(col) is None:
                try:
                    row[col] = cast(rf_val) if rf_val is not None else None
                except (ValueError, TypeError):
                    row[col] = None
        else:
            unmapped.append(rf_key)

    # Promote raw_tags ke kolom dedicated
    for tag_key, device_map in TAGS_TO_COLUMNS.items():
        if dt in device_map and tag_key in rt:
            row[device_map[dt]] = rt[tag_key]

    # NAS disk_id dari raw_tags
    if dt == "nas" and NAS_DISK_ID_TAG in rt:
        row["nas_disk_id"] = rt[NAS_DISK_ID_TAG]

    # Log field yang tidak ada kolom dedicated (untuk deteksi field baru)
    if unmapped:
        log.info(json.dumps({
            "event": "jsonb_only_fields",  # bukan error — disimpan di JSONB
            "device_type": dt,
            "measurement": event.get("measurement"),
            "fields_in_jsonb_only": unmapped
        }))

    return row


def upsert(cursor, row: dict):
    cols = list(row.keys())
    vals = list(row.values())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    update_set = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "event_id"
    )
    sql = f"""
        INSERT INTO dcim_events ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (event_id) DO UPDATE SET
        {update_set}, inserted_at = NOW()
    """
    cursor.execute(sql, vals)


def main():
    conn = psycopg2.connect(
        host=read_secret("pg_host") or "192.168.101.73",
        port=int(read_secret("pg_port") or 5432),
        dbname=read_secret("pg_dbname") or "dcim_sot",
        user=read_secret("pg_user"),
        password=read_secret("pg_password"),
        connect_timeout=10
    )
    conn.autocommit = False
    cur = conn.cursor()

    consumer = KafkaConsumer(
        "dcim.enriched.events",
        bootstrap_servers=["localhost:9092"],
        group_id="dcim-postgres-consumer-v2",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        max_poll_records=100
    )

    log.info(json.dumps({"event": "consumer_started",
                          "topic": "dcim.enriched.events"}))
    batch_size = 50
    batch = []

    for msg in consumer:
        try:
            row = map_event(msg.value)
            batch.append(row)
            if len(batch) >= batch_size:
                for r in batch:
                    upsert(cur, r)
                conn.commit()
                consumer.commit()
                log.info(json.dumps({"event": "batch_committed",
                                      "count": len(batch)}))
                batch.clear()
        except Exception as e:
            conn.rollback()
            log.error(json.dumps({
                "event": "insert_error",
                "error": str(e),
                "event_id": msg.value.get("event_id","?")
            }))

if __name__ == "__main__":
    main()
```

Tampilkan script lengkap dan minta konfirmasi sebelum menulis ke disk.

---

## STEP 5: Systemd Service

```bash
cat > /etc/systemd/system/dcim-postgres-consumer.service << 'EOF'
[Unit]
Description=DCIM PostgreSQL Consumer (Hybrid Schema)
After=network.target

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project/phase2
ExecStart=/usr/bin/python3 dcim_postgres_consumer.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now dcim-postgres-consumer.service
sleep 10
systemctl status dcim-postgres-consumer.service --no-pager
journalctl -u dcim-postgres-consumer.service -n 20 --no-pager
```

---

## STEP 6: Elasticsearch Index Template

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
          "ups_battery_capacity":        {"type": "short"},
          "ups_battery_runtime_sec":     {"type": "integer"},
          "ups_battery_temp":            {"type": "float"},
          "ups_battery_status":          {"type": "short"},
          "ups_input_voltage":           {"type": "float"},
          "ups_output_voltage":          {"type": "float"},
          "ups_output_load":             {"type": "short"},
          "ups_seconds_on_battery":      {"type": "integer"},
          "nas_disk_id":                 {"type": "keyword"},
          "nas_disk_status":             {"type": "short"},
          "nas_disk_temp":               {"type": "float"},
          "nas_system_temp":             {"type": "float"},
          "net_if_name":                 {"type": "keyword"},
          "net_if_oper_status":          {"type": "short"},
          "net_if_admin_status":         {"type": "short"},
          "net_if_in_octets":            {"type": "long"},
          "net_if_out_octets":           {"type": "long"},
          "net_if_in_errors":            {"type": "integer"},
          "net_if_out_errors":           {"type": "integer"},
          "net_if_speed":                {"type": "long"},
          "srv_reading_celsius":         {"type": "float"},
          "srv_upper_threshold_critical":{"type": "float"},
          "srv_power_watts":             {"type": "float"},
          "srv_health":                  {"type": "keyword"},
          "srv_state":                   {"type": "keyword"},
          "cctv_status_online":          {"type": "short"},
          "cctv_status_text":            {"type": "keyword"},
          "raw_fields":                  {"type": "object", "dynamic": true},
          "raw_tags":                    {"type": "object", "dynamic": true}
        }
      }
    }
  }'
```

---

## STEP 7: Validasi End-to-End

### 7a. PostgreSQL — verifikasi per device type
```bash
# Distribusi data
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT device_type, COUNT(*) total,
  COUNT(site) has_site,
  COUNT(enrichment_status) has_enrichment,
  MAX(event_time) latest
FROM dcim_events
GROUP BY device_type ORDER BY total DESC;
"

# UPS — kolom dedicated terisi
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, ups_battery_capacity, ups_battery_temp,
  ups_input_voltage, ups_output_load, ups_seconds_on_battery,
  site, enrichment_status
FROM dcim_events WHERE device_type='ups'
ORDER BY event_time DESC LIMIT 3;
"

# Network — interface status dan traffic
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, net_if_name, net_if_oper_status,
  net_if_in_octets, net_if_out_octets, net_if_in_errors
FROM dcim_events WHERE device_type='network_switch'
ORDER BY event_time DESC LIMIT 3;
"

# CCTV — tidak boleh ada manufacturer printer
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, ip, manufacturer, model,
  cctv_status_online, cctv_status_text, enrichment_status
FROM dcim_events WHERE device_type='cctv'
ORDER BY event_time DESC LIMIT 5;
"

# Field yang hanya di JSONB (informasi, bukan error)
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT device_type,
  jsonb_object_keys(raw_fields) as in_jsonb_only,
  COUNT(*)
FROM dcim_events
GROUP BY device_type, in_jsonb_only
HAVING COUNT(*) > 10
ORDER BY device_type, count DESC;
" | head -30
```

### 7b. Elasticsearch — verifikasi field types dan document count
```bash
# Cek field types kritis
curl -k -u elastic:'<password>' \
  "https://10.70.0.56:9200/dcim-enriched-*/_mapping" \
  | python3 -c "
import sys, json
m = json.load(sys.stdin)
for idx in list(m.keys())[:1]:
    props = m[idx]['mappings'].get('properties',{})
    checks = {
      'event_time': 'date',
      'timestamp': 'date',
      'device_type': 'keyword',
      'metric_value': 'float',
      'ups_battery_capacity': 'short',
      'net_if_in_octets': 'long',
      'cctv_status_online': 'short'
    }
    all_pass = True
    for f, expected in checks.items():
        actual = props.get(f,{}).get('type','MISSING')
        ok = actual == expected
        all_pass = all_pass and ok
        print(f'{'✅' if ok else '❌'} {f}: {actual} (expected {expected})')
    print()
    print('RESULT:', '✅ ALL PASS' if all_pass else '❌ FIX NEEDED')
"

# Document count per device type
curl -k -u elastic:'<password>' \
  "https://10.70.0.56:9200/dcim-enriched-*/_search" \
  -H "Content-Type: application/json" \
  -d '{"size":0,"aggs":{"by_type":{"terms":{"field":"device_type","size":20}}}}' \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
for b in d['aggregations']['by_type']['buckets']:
    print(f'  {b[\"key\"]}: {b[\"doc_count\"]:,} docs')
"
```

### 7c. Cek log consumer untuk field JSONB-only
```bash
journalctl -u dcim-postgres-consumer.service --since "30 min ago" \
  --no-pager | grep "jsonb_only_fields" \
  | python3 -c "
import sys, json
summary = {}
for line in sys.stdin:
    try:
        j = json.loads(line.split(': dcim-postgres')[1].split(': ')[1]
                       if 'dcim-postgres' in line else line.strip())
        dt = j.get('device_type','?')
        fields = j.get('fields_in_jsonb_only', [])
        if dt not in summary:
            summary[dt] = set()
        summary[dt].update(fields)
    except: pass

if summary:
    print('📋 Field yang tersimpan hanya di JSONB (pertimbangkan tambah kolom):')
    for dt, fields in summary.items():
        print(f'  {dt}: {sorted(fields)}')
else:
    print('✅ Semua field sudah terpetakan ke kolom atau masuk JSONB dengan benar')
"
```

**PASS condition:**
- ✅ Semua device type ada di PostgreSQL dengan data terbaru
- ✅ Kolom ups_*, nas_*, net_*, cctv_* non-null untuk device yang sesuai
- ✅ Server ditemukan dan srv_* terisi (jika sample ditemukan di Step 1)
- ✅ CCTV tidak ada manufacturer printer/non-CCTV
- ✅ Elasticsearch: `timestamp` bertipe `date`, bukan `long`
- ✅ `raw_fields` JSONB terisi di setiap row — tidak ada yang kosong

---

## Perbedaan Utama Versi A vs Versi B

| Aspek | Versi A (Full) | Versi B (Rekomendasi) |
|---|---|---|
| Jumlah kolom | ~80+ kolom | ~50 kolom |
| Kolom null | Banyak (sparse) | Minimal |
| Query sederhana | ✅ Semua field langsung | ✅ Field penting langsung |
| Query advanced | ✅ Semua field | ✅ via JSONB (`raw_fields->>'key'`) |
| Data loss | Tidak ada | Tidak ada (JSONB fallback) |
| Maintainability | Lebih berat | Lebih ringan |
| Cocok untuk AI | ✅ | ✅ |
| Cocok untuk alerting | ✅ | ✅ |

---

## CONSTRAINTS
- Baca `dcim_sql_consumer.py` yang sudah ada sebelum membuat script baru
- Kolom `srv_*` **hanya dibuat setelah Step 1a menemukan sample server aktual**
- Jangan DROP tabel yang sudah berisi data — gunakan ALTER TABLE
- Tampilkan script lengkap dan minta konfirmasi sebelum:
  - Menulis file Python
  - Menjalankan CREATE TABLE
  - Me-restart service apapun
- Jika validasi 7c menemukan field JSONB-only yang sering dibutuhkan,
  buat tiket/catatan untuk tambah kolom di iterasi berikutnya
  (ALTER TABLE + update COLUMN_MAP + restart consumer)
```
