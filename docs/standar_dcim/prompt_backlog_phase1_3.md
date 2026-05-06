# Agent Prompt — Backlog Finalisasi DCIM Pipeline (AI/ML Preparation)
> **Referensi Dokumen**: MT-014 v3.0, Doc-24 (Versioning), Doc-29 (Ralph Auto-Update), Doc-30 (Backlog)
> **Tanggal**: 2026-05-04
> **Status Pipeline Aktif**: v3.2.0 — server_deep_sync crontab `*/5 * * * *`
> **Prinsip Utama**: Serial number = Primary Key. PostgreSQL dcim_events = Single Source of Truth.

---

## ⚠️ BACA INI SEBELUM APAPUN

### Kondisi Sistem Saat Ini (per 2026-05-04)
1. **Tabel `dcim_events`** — partitioned, retention 7 hari. Per hari ini **hanya ada data server**, dan masih **banyak kolom NULL**.
2. **Ralph auto-update** — `ralph_cmdb_sync.py` sedang dikembangkan menggunakan `dcim_events` sebagai sumber.
3. **`server_deep_sync.py` v3.2.0** — berjalan setiap 5 menit via crontab (aktif).
4. **Tabel `dcim_server_components`** — sudah ada (Task 1 selesai) sebagai tabel relasional untuk komponen server.
5. **Elasticsearch dashboard** — masih ada issue "No Result Found" di Kibana.
6. **CCTV/NVR** — serial number masih `NO_SN` (Task 7 selesai investigasi, belum fix).

### Aturan Yang Tidak Boleh Dilanggar
- **JANGAN** tulis data dengan `serial_number IN ('NO_SN','NO_IDENTIFIER','','TEMP-')` ke Ralph CMDB
- **JANGAN** hapus data dari `dcim_events` — ini adalah partitioned table dengan retention otomatis
- **JANGAN** ubah schema `dcim_events` tanpa backup terlebih dahulu
- **SELALU** tampilkan output sebelum eksekusi destructive
- **SELALU** ikuti change management: catat versi, timestamp, deskripsi perubahan

---

## FASE 1 — Koreksi PostgreSQL & NULL Values

### Task 1.A — Audit NULL di dcim_events (MULAI DI SINI)

Sebelum melakukan apapun, audit kondisi aktual tabel:

```bash
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
-- Distribusi data per device_type dan tanggal
SELECT
    device_type,
    DATE(event_time) as date,
    COUNT(*) as total_events,
    COUNT(DISTINCT serial_number) as unique_devices,
    -- Cek NULL rate per kolom kritis
    ROUND(100.0 * COUNT(hostname) / COUNT(*), 1) as hostname_fill_pct,
    ROUND(100.0 * COUNT(site) / COUNT(*), 1) as site_fill_pct,
    ROUND(100.0 * COUNT(rack_name) / COUNT(*), 1) as rack_fill_pct,
    ROUND(100.0 * COUNT(enrichment_status) / COUNT(*), 1) as enrichment_fill_pct,
    -- Device-specific NULL check
    ROUND(100.0 * COUNT(ups_battery_capacity) / COUNT(*), 1) as ups_battery_fill_pct,
    ROUND(100.0 * COUNT(nas_disk_temp) / COUNT(*), 1) as nas_temp_fill_pct,
    ROUND(100.0 * COUNT(net_if_oper_status) / COUNT(*), 1) as net_if_fill_pct,
    ROUND(100.0 * COUNT(srv_reading_celsius) / COUNT(*), 1) as srv_temp_fill_pct,
    ROUND(100.0 * COUNT(cctv_status_online) / COUNT(*), 1) as cctv_fill_pct
FROM dcim_events
WHERE event_time > NOW() - INTERVAL '24 hours'
GROUP BY device_type, DATE(event_time)
ORDER BY device_type, date DESC;
"

# Cek juga tabel dcim_server_components
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT
    component_type,
    COUNT(*) as total,
    COUNT(DISTINCT server_serial_number) as unique_servers,
    COUNT(model_name) as has_model,
    COUNT(serial_number) as has_serial
FROM dcim_server_components
GROUP BY component_type;
" 2>/dev/null || echo "Table dcim_server_components not found or empty"
```

**STOP** — laporkan seluruh output sebelum lanjut. Ini menentukan langkah selanjutnya.

---

### Task 1.B — Diagnosis Mengapa Hanya Server yang Ada di dcim_events

```bash
# Cek apakah Telegraf aktif untuk semua device type
sudo systemctl status telegraf --no-pager | head -10

# Cek topics Kafka — apakah semua raw topics aktif
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --list --bootstrap-server localhost:9092 | grep dcim.raw

# Cek message count per topic (apakah ada data mengalir)
for TOPIC in dcim.raw.network.snmp dcim.raw.network.interfaces \
             dcim.raw.power.ups dcim.raw.storage.nas \
             dcim.raw.server dcim.raw.device.isapi; do
  COUNT=$(docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic $TOPIC --max-messages 3 \
    --timeout-ms 5000 2>/dev/null | wc -l)
  echo "Topic $TOPIC: $COUNT messages received"
done

# Cek normalizer — apakah process semua topic
sudo journalctl -u dcim-normalizer --since "30 minutes ago" --no-pager \
  | grep -iE "device_type|error|warn|ups|nas|cctv|network" | tail -20

# Cek SQL consumer — apakah menulis ke dcim_events
sudo journalctl -u dcim-sql-consumer --since "30 minutes ago" --no-pager \
  | tail -20
```

Berdasarkan hasil diagnosis, **fix pipeline** agar semua device type masuk ke `dcim_events`:

**Jika topic aktif tapi tidak ada di dcim_events** → cek SQL consumer mapping untuk device type tersebut
**Jika topic tidak aktif** → cek Telegraf config file untuk device type tersebut
**Jika normalizer skip device type** → cek `metric_mapping.json` dan `topic_to_device_type` config

---

### Task 1.C — Fix NULL Values di dcim_events

Setelah semua device type mengalir, NULL values terjadi karena dua alasan:

**Alasan A**: Field device-specific NULL untuk row yang bukan device tersebut → **NORMAL, jangan diubah**
**Alasan B**: Field yang seharusnya terisi tapi NULL → **FIX INI**

```bash
# Identifikasi Alasan B — field yang seharusnya terisi tapi NULL
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
-- UPS rows dengan ups_battery_capacity NULL
SELECT COUNT(*) as ups_with_null_battery
FROM dcim_events
WHERE device_type = 'ups'
  AND ups_battery_capacity IS NULL
  AND event_time > NOW() - INTERVAL '24 hours';

-- Network rows dengan net_if_oper_status NULL
SELECT COUNT(*) as net_with_null_status
FROM dcim_events
WHERE device_type = 'network_switch'
  AND net_if_oper_status IS NULL
  AND event_time > NOW() - INTERVAL '24 hours';

-- Cek raw_fields apakah field ada tapi tidak di-mapping
SELECT device_type,
       raw_fields->>'upsBatteryCapacity' as ups_battery_in_json,
       ups_battery_capacity as ups_battery_in_col
FROM dcim_events
WHERE device_type = 'ups'
  AND event_time > NOW() - INTERVAL '1 hour'
LIMIT 5;
"
```

Jika field ada di `raw_fields` JSONB tapi tidak di kolom dedicated → update `RAW_FIELD_MAP` di `dcim_postgres_consumer.py` dan tambahkan kolom jika belum ada.

Tampilkan perubahan sebelum eksekusi. Restart consumer setelah update:
```bash
sudo systemctl restart dcim-sql-consumer
```

---

## FASE 2 — Validasi Streaming & Fix Elasticsearch

### Task 2.A — Kafka Pipeline End-to-End Validation

```bash
echo "=== KAFKA END-TO-END VALIDATION ==="
echo "Timestamp: $(date)"

# Layer 1: Raw topics
echo ""
echo "--- Layer 1: Raw Topics ---"
for TOPIC in dcim.raw.network.snmp dcim.raw.power.ups \
             dcim.raw.storage.nas dcim.raw.server dcim.raw.device.isapi; do
  MSG=$(docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic $TOPIC \
    --max-messages 1 --timeout-ms 8000 2>/dev/null)
  if [ -n "$MSG" ]; then
    DT=$(echo "$MSG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tags',{}).get('device_type','?'))" 2>/dev/null)
    echo "  ✅ $TOPIC → device_type=$DT"
  else
    echo "  ❌ $TOPIC → NO DATA"
  fi
done

# Layer 2: Normalized topic
echo ""
echo "--- Layer 2: Normalized Topic ---"
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.normalized.events \
  --max-messages 10 --timeout-ms 15000 2>/dev/null \
  | python3 -c "
import sys, json
from collections import Counter
types = Counter()
for line in sys.stdin:
    try:
        d = json.loads(line)
        types[d.get('device_type','unknown')] += 1
    except: pass
print('  Device types in normalized topic:')
for dt, count in types.most_common():
    print(f'    {\"✅\" if dt not in (\"unknown\",None) else \"⚠️\"} {dt}: {count} events')
"

# Layer 3: Enriched topic
echo ""
echo "--- Layer 3: Enriched Topic ---"
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 20 --timeout-ms 15000 2>/dev/null \
  | python3 -c "
import sys, json
from collections import defaultdict
stats = defaultdict(lambda: {'count':0,'full':0,'partial':0,'no_id':0})
for line in sys.stdin:
    try:
        d = json.loads(line)
        dt = d.get('device_type','unknown')
        stats[dt]['count'] += 1
        es = d.get('enrichment_status','')
        if es == 'FULL': stats[dt]['full'] += 1
        elif es == 'PARTIAL': stats[dt]['partial'] += 1
        elif es == 'NO_IDENTIFIER': stats[dt]['no_id'] += 1
    except: pass
print('  Enriched events by device type:')
for dt, s in stats.items():
    t = s['count']
    print(f'    {dt}: {t} events | FULL:{s[\"full\"]} PARTIAL:{s[\"partial\"]} NO_ID:{s[\"no_id\"]}')
"

# Layer 4: Consumer lag
echo ""
echo "--- Layer 4: Consumer Lag ---"
docker exec kafka-broker /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --all-groups 2>/dev/null \
  | grep -E "GROUP|dcim|nifi|telegraf" | head -20
```

---

### Task 2.B — Fix Elasticsearch Index & Dashboard

```bash
# Step 1: Cek index mana yang aktif dan berisi data
curl -s "http://10.70.0.56:9200/_cat/indices/dcim-enriched-*?v&h=index,docs.count,store.size,health" \
  | sort -k2 -rn | head -10

# Step 2: Cek field mapping aktual
LATEST_IDX=$(curl -s "http://10.70.0.56:9200/_cat/indices/dcim-enriched-*?h=index" \
  | sort | tail -1 | tr -d ' ')
echo "Latest index: $LATEST_IDX"

curl -s "http://10.70.0.56:9200/${LATEST_IDX}/_mapping" \
  | python3 -c "
import sys, json
m = json.load(sys.stdin)
idx = list(m.keys())[0]
props = m[idx]['mappings'].get('properties', {})

# Temukan apakah field ada di root atau di dalam 'tag'
print('=== Field Location Check ===')
check_fields = ['device_type','hostname','site','rack_name',
                'enrichment_status','metric_value','ups_battery_capacity']
for f in check_fields:
    in_root = f in props
    in_tag = f in props.get('tag',{}).get('properties',{})
    loc = 'ROOT' if in_root else ('tag.'+f if in_tag else 'NOT FOUND')
    ftype = (props.get(f,{}).get('type') or
             props.get('tag',{}).get('properties',{}).get(f,{}).get('type','?'))
    print(f'  {f}: location={loc}, type={ftype}')
"

# Step 3: Sample dokumen untuk lihat struktur aktual
curl -s "http://10.70.0.56:9200/${LATEST_IDX}/_search?size=1" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
hits = d.get('hits',{}).get('hits',[])
if hits:
    src = hits[0].get('_source',{})
    print('=== Actual Document Structure ===')
    print(json.dumps({k: str(type(v).__name__)+':'+str(v)[:50]
                     for k,v in src.items()}, indent=2))
"
```

Berdasarkan hasil di atas:

**Jika field ada di `tag.device_type`** (nested):
```bash
# Update Kibana index pattern untuk pakai field yang benar
# Di script create_kibana_dashboard.py: FIELD_PREFIX = "tag."
```

**Jika field ada di root `device_type`** (flat):
```bash
# Di script create_kibana_dashboard.py: FIELD_PREFIX = ""
```

**Jika index kosong atau tidak ada data terbaru**:
```bash
# Cek telegraf-consumer apakah masih running dan menulis ke ES
sudo systemctl status telegraf-consumer --no-pager | head -10
sudo journalctl -u telegraf-consumer --since "10 minutes ago" --no-pager | tail -20
```

**Fix Kibana Dashboard** — setelah field structure dikonfirmasi:
```bash
# Jalankan script dengan FIELD_PREFIX yang benar
python3 /home/infra/dcim_metrics_project/scripts/create_kibana_dashboard.py

# Verifikasi dashboard tersimpan
curl -s "http://10.70.0.56:5601/api/saved_objects/_find?type=dashboard" \
  -H "kbn-xsrf: true" \
  | python3 -m json.tool | grep -E '"title"|"id"'
```

---

## FASE 3 — AI/ML Data Readiness

### Task 3.A — AI-Ready Schema Verification

```bash
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
-- Cek relasi antar tabel
SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS foreign_table,
    ccu.column_name AS foreign_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.referential_constraints rc
    ON tc.constraint_name = rc.constraint_name
LEFT JOIN information_schema.constraint_column_usage ccu
    ON rc.unique_constraint_name = ccu.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.table_name IN ('dcim_events','dcim_server_components','device_metrics','unified_assets')
ORDER BY tc.table_name, tc.constraint_type;

-- Cek tipe data kolom numerik (penting untuk ML)
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'dcim_events'
  AND data_type IN ('numeric','integer','bigint','smallint','double precision','real')
ORDER BY column_name;

-- Statistik data quality per device type
SELECT
    device_type,
    COUNT(*) as total_rows,
    COUNT(DISTINCT serial_number) as unique_assets,
    COUNT(DISTINCT DATE(event_time)) as days_of_data,
    MIN(event_time) as oldest_event,
    MAX(event_time) as newest_event,
    ROUND(AVG(CASE WHEN enrichment_status = 'FULL' THEN 1 ELSE 0 END) * 100, 1) as pct_full_enrichment
FROM dcim_events
GROUP BY device_type
ORDER BY device_type;
"
```

### Task 3.B — Verifikasi Tabel dcim_server_components untuk AI

```bash
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
-- Cek kelengkapan data komponen server
SELECT
    component_type,
    COUNT(*) as total_components,
    COUNT(DISTINCT server_serial_number) as servers_covered,
    ROUND(100.0 * COUNT(model_name) / COUNT(*), 1) as model_fill_pct,
    ROUND(100.0 * COUNT(serial_number) / COUNT(*), 1) as serial_fill_pct,
    ROUND(100.0 * COUNT(size_value) / COUNT(*), 1) as size_fill_pct
FROM dcim_server_components
GROUP BY component_type;

-- Contoh join dcim_events + dcim_server_components untuk AI feature view
SELECT
    e.serial_number,
    e.hostname,
    e.site,
    e.rack_name,
    e.srv_reading_celsius as temperature,
    e.srv_power_watts as power_w,
    e.event_time,
    -- Dari tabel komponen
    c.component_type,
    c.model_name as component_model,
    c.size_value
FROM dcim_events e
LEFT JOIN dcim_server_components c
    ON e.serial_number = c.server_serial_number
WHERE e.device_type IN ('server','server_redfish')
  AND e.event_time > NOW() - INTERVAL '1 hour'
ORDER BY e.event_time DESC
LIMIT 10;
"
```

### Task 3.C — Update Dokumentasi Arsitektur (Task 3 di Backlog)

Setelah semua fix selesai, update dokumen arsitektur:

```bash
# Buat summary perubahan untuk dicatat
cat > /home/infra/dcim_metrics_project/docs/CHANGELOG_$(date +%Y%m%d).md << 'EOF'
# Change Log - $(date +%Y-%m-%d)

## Versi: v3.3.0

### Perubahan Utama
1. **PostgreSQL dcim_events**: Fix NULL values untuk semua device type
   - Semua device type (UPS, NAS, Network, Server, CCTV) kini mengalir ke dcim_events
   - NULL rate < 10% untuk field mandatory per device type

2. **Elasticsearch**: Fix index mapping dan Kibana dashboard
   - Index template dcim-enriched-v2 aktif
   - Dashboard DCIM Infrastructure Overview tersedia di Kibana

3. **AI/ML Readiness**: Schema dcim_events + dcim_server_components terverifikasi
   - Tipe data numerik akurat
   - Relasi tabel logis
   - Data quality > 90% untuk server dan network_switch

### Status per Device Type
| Device Type | dcim_events | Ralph Sync | Kibana Dashboard |
|---|---|---|---|
| server | ✅ | ✅ server_deep_sync v3.2.0 | ✅ |
| network_switch | ? | ? | ? |
| ups | ? | ? | ? |
| nas | ? | ? | ? |
| cctv | ⚠️ NO_SN issue | ❌ skip | ⚠️ |
| nvr | ⚠️ NO_SN issue | ❌ skip | ⚠️ |

### Referensi
- MT-014 v3.0 — Pipeline architecture
- Doc-24 — Versioning standard
- Doc-29 — Ralph auto-update capabilities
- Doc-30 — AI/ML preparation backlog
EOF
```

---

## FASE 3.D — Ralph CMDB Sync untuk Non-Server Devices

Berdasarkan Doc-29, sinkronisasi untuk UPS, NAS, dan Network Switch sudah
didefinisikan. Yang perlu dilakukan adalah memastikan `ralph_cmdb_sync.py`
sudah menghandle semua device type ini dari `dcim_events`.

```bash
# Cek isi ralph_cmdb_sync.py saat ini
cat /home/infra/dcim_metrics_project/scripts/ralph_cmdb_sync.py 2>/dev/null | head -100

# Apakah sudah ada sync untuk UPS?
grep -n "ups\|UPS" /home/infra/dcim_metrics_project/scripts/ralph_cmdb_sync.py 2>/dev/null

# Apakah sudah ada sync untuk NAS?
grep -n "nas\|NAS" /home/infra/dcim_metrics_project/scripts/ralph_cmdb_sync.py 2>/dev/null
```

Berdasarkan hasil di atas, tambahkan sync logic untuk device type yang belum ada.
Ikuti skema dari Doc-29:

**UPS** — field yang di-sync: hostname, firmware (dari `ups_firmware`),
management IP (dari `ip`), model (dari `ups_model_snmp` atau `model`)

**NAS** — field yang di-sync: hostname, firmware (dari `raw_tags->>'firmware'`),
management IP, serial number (sebagai lookup key), model, manufacturer

**Network Switch** — field yang di-sync: hostname, firmware (dari `raw_tags->>'firmware'`),
management IP, serial number, model, manufacturer

```python
# Template sync function untuk non-server devices
def sync_device_to_ralph(pg_conn, ralph_client, device_type: str,
                          firmware_col: str = None) -> dict:
    """
    Generic sync function untuk UPS, NAS, Network Switch.
    Mengambil data terbaru dari dcim_events per serial_number.
    """
    cursor = pg_conn.cursor(cursor_factory=RealDictCursor)

    # Query data terbaru per device, hanya yang punya SN valid
    cursor.execute(f"""
        SELECT DISTINCT ON (serial_number)
            serial_number, hostname, ip, model, manufacturer,
            site, rack_name, asset_status, enrichment_status,
            event_time,
            raw_tags,
            {firmware_col or 'NULL'} as firmware_version
        FROM dcim_events
        WHERE device_type = %s
          AND event_time > NOW() - INTERVAL '24 hours'
          AND serial_number IS NOT NULL
          AND serial_number NOT IN ('NO_SN','NO_IDENTIFIER','','TEMP-')
          AND hostname NOT IN ('unknown','')
          AND ip IS NOT NULL
        ORDER BY serial_number, event_time DESC
    """, (device_type,))

    devices = cursor.fetchall()
    stats = {"synced": 0, "skipped": 0, "failed": 0}

    for device in devices:
        sn = device['serial_number']

        # Cari di Ralph via serial number
        ralph_asset = find_asset_in_ralph(sn, ralph_client)
        if not ralph_asset:
            log.warning(f"Asset not in Ralph: {sn} ({device['hostname']})")
            stats["skipped"] += 1
            continue

        # Bangun payload — hanya field yang ada nilainya
        payload = {}
        if device.get('hostname'):
            payload['hostname'] = device['hostname']
        if device.get('firmware_version'):
            payload['firmware_version'] = str(device['firmware_version'])

        # Firmware dari raw_tags jika tidak ada di kolom dedicated
        if not payload.get('firmware_version') and device.get('raw_tags'):
            raw_tags = device['raw_tags']
            if isinstance(raw_tags, str):
                import json
                raw_tags = json.loads(raw_tags)
            fw = raw_tags.get('firmware')
            if fw:
                payload['firmware_version'] = str(fw)

        # Management IP via IPAddress object
        if device.get('ip'):
            sync_management_ip(ralph_asset['id'], device['ip'],
                               device['hostname'], ralph_client)

        if payload:
            success = update_ralph_asset(ralph_asset['id'], payload, ralph_client)
            if success:
                stats["synced"] += 1
            else:
                stats["failed"] += 1

    return stats
```

**Tampilkan perubahan lengkap pada `ralph_cmdb_sync.py` sebelum menulis.**
**Minta konfirmasi sebelum eksekusi.**

---

## Validasi Akhir — Semua Fase

Jalankan setelah semua fase selesai:

```bash
echo "========================================="
echo "  DCIM PIPELINE — FINAL VALIDATION"
echo "  $(date)"
echo "========================================="

echo ""
echo "1. PostgreSQL dcim_events Coverage:"
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT device_type,
  COUNT(DISTINCT serial_number) as unique_devices,
  COUNT(*) as total_events,
  MAX(event_time) as latest,
  ROUND(100.0 * SUM(CASE WHEN enrichment_status='FULL' THEN 1 ELSE 0 END)/COUNT(*),1) as pct_full
FROM dcim_events
WHERE event_time > NOW() - INTERVAL '2 hours'
GROUP BY device_type ORDER BY device_type;
" 2>/dev/null

echo ""
echo "2. Kafka Pipeline Health:"
docker exec kafka-broker /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --all-groups 2>/dev/null \
  | awk 'NR==1 || /LAG/ || /nifi|telegraf|dcim/' | head -15

echo ""
echo "3. Elasticsearch Status:"
curl -s "http://10.70.0.56:9200/_cat/indices/dcim-enriched-*?v&h=index,docs.count,health" \
  | sort -k2 -rn | head -5

echo ""
echo "4. Ralph Sync Last Run:"
tail -5 /home/infra/dcim_metrics_project/logs/ralph_sync.log 2>/dev/null \
  | python3 -c "
import sys, json
for line in sys.stdin:
    try:
        j_start = line.find('{')
        if j_start >= 0:
            d = json.loads(line[j_start:])
            print(f'  {d.get(\"event\",\"?\")} | {d.get(\"stats\",d.get(\"timestamp\",\"\"))}')
    except: pass
" 2>/dev/null

echo ""
echo "5. Active Services:"
for SVC in telegraf dcim-normalizer dcim-enrichment-api dcim-redis-sync \
           telegraf-consumer dcim-sql-consumer dcim-ralph-sync.timer; do
  STATUS=$(systemctl is-active $SVC 2>/dev/null)
  ICON=$([ "$STATUS" = "active" ] && echo "✅" || echo "❌")
  echo "  $ICON $SVC: $STATUS"
done

echo ""
echo "6. Crontab Active:"
crontab -l 2>/dev/null | grep -v "^#" | grep "dcim\|ralph\|sync"

echo ""
echo "========================================="
echo "  PASS CONDITIONS:"
echo "  ✅ All 5+ device types in dcim_events"
echo "  ✅ Enrichment FULL > 80% per device type"
echo "  ✅ Kafka consumer lag = 0"
echo "  ✅ Elasticsearch has docs in latest index"
echo "  ✅ All services active"
echo "========================================="
```

---

## Change Log Wajib Setelah Selesai

Sesuai standar Doc-24, setelah semua perubahan selesai:

```bash
# Catat versi baru
CURRENT_VERSION="v3.3.0"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M WIB')

echo "Tambahkan ke tabel Log Perubahan Sistem di doc 24-versioning-change-management-standard.md:"
echo "| $CURRENT_VERSION | $TIMESTAMP | Backlog Doc-30 Fase 1-3: Fix NULL dcim_events, Fix ES dashboard, AI/ML readiness verification, Ralph sync untuk UPS/NAS/Switch | Active |"

# Git commit
cd /home/infra/dcim_metrics_project
git add -A
git commit -m "v3.3.0: Backlog Doc-30 completion — fix dcim_events NULLs, ES dashboard, Ralph sync all device types, AI/ML verification"
git tag v3.3.0
git log --oneline -5
```

---

## CONSTRAINTS KESELURUHAN

| Aturan | Detail |
|---|---|
| Urutan eksekusi | Fase 1 → Fase 2 → Fase 3. Jangan loncat fase |
| Audit dulu | Task 1.A WAJIB dijalankan dan dilaporkan sebelum apapun |
| Confirm sebelum write | Tampilkan semua perubahan script/SQL sebelum eksekusi |
| Jangan hapus data | dcim_events adalah partitioned — biarkan retention otomatis yang urus |
| SN validation | Semua sync ke Ralph WAJIB filter `serial_number NOT IN ('NO_SN','NO_IDENTIFIER','')` |
| Change log | Setiap perubahan WAJIB dicatat versi + timestamp sesuai Doc-24 |
| Restart order | Ikuti urutan restart dari MT-014 Sec 8: redis-sync → enrichment-api → NiFi → normalizer → consumers |
| Konfirmasi crontab | Jangan tambah atau hapus crontab tanpa konfirmasi operator |
```
