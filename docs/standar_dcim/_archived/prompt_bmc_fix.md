# Agent Prompt — Fix BMC Lockout & Konsolidasi Arsitektur Server Polling

> **Konteks**: Agent sudah mengidentifikasi root cause dengan benar.
> Telegraf (interval 20s) + dcim_inventory_poller.py berjalan bersamaan
> mem-polling Redfish BMC Lenovo yang sama → menyebabkan lockout.
> Prompt ini mengonfirmasi arah perbaikan dan memberikan batasan yang jelas.

---

## Konfirmasi: Ya, Lanjutkan Rencana Kamu

Analisismu benar. Lakukan perubahan berikut dengan urutan yang ketat.
**Jangan skip langkah dan jangan eksekusi tanpa menampilkan perubahan lebih dulu.**

---

## LANGKAH 1 — Hentikan Semua Akses ke BMC Sekarang

Sebelum mengubah apapun, pastikan tidak ada proses yang menyentuh BMC.

```bash
# Stop semua yang mungkin menyentuh Redfish
systemctl stop telegraf
pkill -f dcim_inventory_poller 2>/dev/null
pkill -f redfish 2>/dev/null
sleep 5

# Verifikasi tidak ada koneksi aktif ke IP BMC server
ss -tnp | grep -E "10\.50\.0\.[2-6]|:443" | grep -v LISTEN

# Pastikan kedua proses benar-benar berhenti
systemctl status telegraf --no-pager | head -5
ps aux | grep -iE "poller|redfish|ipmi" | grep -v grep
```

Tunggu **minimal 15 menit** sebelum mencoba koneksi apapun ke BMC.
Jangan lanjut ke Langkah 2 sebelum timer selesai.

---

## LANGKAH 2 — Perbaiki Interval Telegraf Redfish

Tampilkan isi file `/etc/telegraf/telegraf.d/servers-redfish.conf` dulu,
lalu ubah **semua** nilai `interval` dari `20s` menjadi `120s`.

```bash
# Backup dulu sebelum edit
cp /etc/telegraf/telegraf.d/servers-redfish.conf \
   /etc/telegraf/telegraf.d/servers-redfish.conf.bak.$(date +%Y%m%d)

# Tampilkan isi file saat ini
cat /etc/telegraf/telegraf.d/servers-redfish.conf
```

Setelah melihat isinya, lakukan perubahan berikut:

```toml
# Ubah semua instance ini:
interval = "20s"   →   interval = "120s"

# Tambahkan timeout yang lebih panjang dari interval sebelumnya:
timeout = "30s"

# Pastikan tidak ada parallel requests ke server yang sama:
# Jika ada multiple [[inputs.redfish]] block untuk server yang berbeda,
# tambahkan offset agar tidak polling bersamaan:
# Server 1: interval = "120s", collection_offset = "0s"
# Server 2: interval = "120s", collection_offset = "20s"
# Server 3: interval = "120s", collection_offset = "40s"
# dst — jarak 20 detik antar server
```

**Tampilkan file hasil perubahan sebelum menyimpan. Minta konfirmasi.**

---

## LANGKAH 3 — Hapus Polling Server dari dcim_inventory_poller.py

Sesuai rencanamu: Telegraf yang polling Redfish, poller Python hanya sync ke Ralph
menggunakan data dari database.

```bash
# Tampilkan bagian server polling di poller dulu
grep -n -A 20 -E "redfish|server|10\.50\.0\.[2-6]|def.*server|def.*poll" \
  /home/infra/dcim_metrics_project/phase2/dcim_inventory_poller.py \
  | head -80
```

Setelah melihat kode aslinya, lakukan perubahan ini:

### Yang DIHAPUS dari poller:
- Semua fungsi yang memanggil Redfish API secara langsung
- Semua `requests.get()` ke IP BMC server
- Semua retry logic untuk Redfish

### Yang DITAMBAHKAN ke poller:
Fungsi untuk membaca data server dari PostgreSQL (hasil Telegraf):

```python
def get_server_data_from_db(pg_conn) -> list:
    """
    Ambil data server terbaru dari PostgreSQL.
    Data ini adalah hasil Telegraf Redfish — tidak perlu polling BMC lagi.
    
    PENTING: Hanya ambil data yang memenuhi mandatory fields.
    Jangan sync ke Ralph jika field wajib tidak lengkap.
    """
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT DISTINCT ON (serial_number)
            serial_number,
            hostname,
            ip,
            model,
            manufacturer,
            site,
            rack_name,
            asset_status,
            event_time,
            enrichment_status,
            raw_fields
        FROM dcim_events
        WHERE device_type IN ('server', 'server_redfish')
          AND serial_number IS NOT NULL
          AND serial_number NOT IN ('NO_SN', 'NO_IDENTIFIER', '', 'TEMP-')
          AND hostname IS NOT NULL
          AND hostname NOT IN ('unknown', '')
          AND ip IS NOT NULL
          AND model IS NOT NULL
          AND model NOT IN ('unknown', '')
          -- Hanya ambil data yang segar (maksimal 10 menit terakhir dari Telegraf)
          AND event_time > NOW() - INTERVAL '10 minutes'
        ORDER BY serial_number, event_time DESC
    """)
    
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    
    result = []
    for row in rows:
        data = dict(zip(columns, row))
        # Tandai bahwa ini data dari DB bukan live device
        data['data_source'] = 'telegraf_via_db'
        data['_skip_if_stale'] = False  # data segar, aman untuk sync ke Ralph
        result.append(data)
    
    if not result:
        log.warning(json.dumps({
            "event": "no_fresh_server_data_in_db",
            "message": "Telegraf mungkin belum polling atau BMC masih terkunci",
            "action": "skipping_ralph_sync_for_servers"
        }))
    
    return result


def get_server_last_known(pg_conn) -> list:
    """
    Fallback: ambil data server terakhir yang diketahui (bisa lebih dari 10 menit).
    Data ini HANYA untuk display/logging — TIDAK dipakai untuk update Ralph CMDB.
    """
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT DISTINCT ON (serial_number)
            serial_number, hostname, ip, model,
            event_time, enrichment_status
        FROM dcim_events
        WHERE device_type IN ('server', 'server_redfish')
          AND serial_number NOT IN ('NO_SN', 'NO_IDENTIFIER', '', 'TEMP-')
          AND hostname NOT IN ('unknown', '')
        ORDER BY serial_number, event_time DESC
    """)
    
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    result = []
    for row in rows:
        data = dict(zip(columns, row))
        data['data_source'] = 'historical_db'
        data['_skip_cmdb_update'] = True  # JANGAN tulis ke Ralph
        result.append(data)
    
    return result
```

### Update alur sync server ke Ralph:

```python
def sync_servers_to_ralph(pg_conn, ralph_client):
    """
    Sync data server ke Ralph CMDB.
    Sumber: PostgreSQL (hasil Telegraf), bukan Redfish langsung.
    """
    # Coba ambil data segar dulu
    servers = get_server_data_from_db(pg_conn)
    
    if not servers:
        # Tidak ada data segar — ambil last known untuk logging saja
        last_known = get_server_last_known(pg_conn)
        if last_known:
            log.warning(json.dumps({
                "event": "using_last_known_server_data",
                "count": len(last_known),
                "action": "display_only_not_syncing_to_ralph",
                "servers": [s['serial_number'] for s in last_known]
            }))
        # Return tanpa update Ralph — tidak ada data fresh
        return
    
    for server in servers:
        # Double-check: jangan pernah tulis data stale ke Ralph
        if server.get('_skip_cmdb_update'):
            log.info(f"Skipping Ralph update for {server.get('serial_number')} - stale data")
            continue
        
        # Validasi mandatory fields sekali lagi sebelum sync
        mandatory = {
            'serial_number': server.get('serial_number'),
            'hostname': server.get('hostname'),
            'ip': server.get('ip'),
            'model': server.get('model')
        }
        
        invalid = {k: v for k, v in mandatory.items()
                   if not v or v in ('unknown', 'NO_SN', 'TEMP-', '')}
        
        if invalid:
            log.error(json.dumps({
                "event": "mandatory_field_missing_skip_ralph",
                "serial_number": server.get('serial_number'),
                "missing": invalid
            }))
            continue
        
        # Safe to sync to Ralph
        try:
            ralph_client.update_asset(server)
            log.info(json.dumps({
                "event": "ralph_sync_success",
                "serial_number": server['serial_number'],
                "hostname": server['hostname'],
                "data_source": server['data_source']
            }))
        except Exception as e:
            log.error(json.dumps({
                "event": "ralph_sync_failed",
                "serial_number": server.get('serial_number'),
                "error": str(e)
            }))
```

**Tampilkan diff lengkap sebelum menulis ke file. Minta konfirmasi.**

---

## LANGKAH 4 — Verifikasi BMC Sudah Unlock (Setelah 15 Menit)

Setelah menunggu minimal 15 menit dari Langkah 1:

```bash
# Test SATU request saja — jangan loop, jangan retry
BMC_IP="10.50.0.2"  # ganti dengan IP server pertama
BMC_USER="<user>"
BMC_PASS="<password>"

HTTP_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" \
  -u "${BMC_USER}:${BMC_PASS}" \
  "https://${BMC_IP}/redfish/v1/" \
  --max-time 15 --connect-timeout 10)

echo "BMC Response: $HTTP_CODE"

case $HTTP_CODE in
  200) echo "✅ BMC UNLOCKED — aman untuk restart Telegraf" ;;
  401) echo "❌ Auth failed — cek credential atau masih terkunci" ;;
  403) echo "❌ Masih terkunci — tunggu 15 menit lagi" ;;
  000) echo "❌ Tidak ada respons — network issue atau BMC hang" ;;
  *)   echo "⚠️  Response tidak terduga: $HTTP_CODE" ;;
esac
```

**Jangan lanjut ke Langkah 5 jika HTTP code bukan 200.**

Jika masih 401/403 setelah 30 menit total:
- Kemungkinan perlu reset BMC lockout via konsol fisik atau iKVM
- Laporkan ke operator — jangan coba akses programmatik lagi

---

## LANGKAH 5 — Restart Telegraf dengan Interval Baru

Hanya jalankan ini setelah Langkah 4 mengonfirmasi BMC unlocked (HTTP 200):

```bash
# Verifikasi config sudah benar sebelum start
telegraf --config /etc/telegraf/telegraf.conf \
         --config-directory /etc/telegraf/telegraf.d \
         --test 2>&1 | grep -iE "redfish|error|warn" | head -20

# Start Telegraf
systemctl start telegraf
sleep 30

# Cek status
systemctl status telegraf --no-pager | head -15

# Monitor log selama 2 menit — pastikan tidak ada auth error
journalctl -u telegraf -f --no-pager &
TAIL_PID=$!
sleep 120
kill $TAIL_PID

# Cek apakah ada error BMC
journalctl -u telegraf --since "3 minutes ago" --no-pager \
  | grep -iE "error|401|403|lockout|timeout" | head -20
```

---

## LANGKAH 6 — Verifikasi Data Server Masuk ke Pipeline

Setelah Telegraf berjalan dengan interval baru:

```bash
# Tunggu satu siklus polling (130 detik untuk interval 120s + buffer)
sleep 130

# Cek apakah data server masuk ke Kafka
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.enriched.events \
  --max-messages 50 --timeout-ms 15000 2>/dev/null \
  | python3 -c "
import sys, json
servers = []
for line in sys.stdin:
    try:
        d = json.loads(line.strip())
        if d.get('device_type') in ('server','server_redfish'):
            servers.append({
                'hostname': d.get('hostname'),
                'serial_number': d.get('serial_number'),
                'ip': d.get('ip'),
                'model': d.get('model'),
                'site': d.get('site'),
                'enrichment_status': d.get('enrichment_status'),
                'event_time': d.get('event_time')
            })
    except: pass

if servers:
    print(f'✅ Ditemukan {len(servers)} server events')
    for s in servers[:3]:
        print(json.dumps(s, indent=2))
else:
    print('❌ Tidak ada data server — Telegraf belum polling atau pipeline error')
"

# Verifikasi data server ada di PostgreSQL
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "
SELECT hostname, serial_number, ip, model, event_time, enrichment_status
FROM dcim_events
WHERE device_type IN ('server','server_redfish')
  AND serial_number NOT IN ('NO_SN','NO_IDENTIFIER','')
ORDER BY event_time DESC
LIMIT 5;
"
```

---

## LANGKAH 7 — Test Ralph Sync dari Database (bukan dari BMC)

```bash
# Jalankan poller dengan mode dry-run dulu untuk verifikasi
python3 /home/infra/dcim_metrics_project/phase2/dcim_inventory_poller.py \
  --dry-run --device-type server 2>&1 | head -40

# Jika dry-run berhasil dan data terlihat benar, jalankan full sync
# python3 /home/infra/dcim_metrics_project/phase2/dcim_inventory_poller.py \
#   --device-type server
```

**Pastikan output dry-run menunjukkan:**
- `data_source: telegraf_via_db` (bukan `live_redfish`)
- Semua mandatory fields terisi (serial_number, hostname, ip, model)
- Tidak ada `TEMP-` prefix di serial_number
- Tidak ada `_skip_cmdb_update: True` di data yang akan di-sync

---

## Batasan yang Tidak Boleh Dilanggar

| Aturan | Alasan |
|---|---|
| Satu proses saja yang akses Redfish per server | Mencegah BMC lockout berulang |
| Interval Telegraf minimal 120s untuk Redfish | BMC Lenovo XCC butuh waktu recovery antar request |
| Data historis TIDAK masuk ke Ralph CMDB | Mencegah data stale menjadi "kebenaran" di CMDB |
| Mandatory fields harus lengkap sebelum Ralph sync | Serial number adalah primary key — tidak boleh salah |
| Jangan retry BMC lebih dari sekali per 15 menit | Setiap retry saat lockout memperpanjang lockout |

---

## Arsitektur Final yang Diinginkan

```
BMC Server (Lenovo XCC)
        ↓ Redfish (interval 120s, 1 proses saja)
    Telegraf
        ↓ Influx Line Protocol
Kafka: dcim.raw.server.*
        ↓
Python Normalizer
        ↓
Kafka: dcim.normalized.events
        ↓
NiFi Enrichment
        ↓
Kafka: dcim.enriched.events
        ↓              ↓
PostgreSQL          Elasticsearch
(dcim_events)      (dcim-enriched-*)
        ↓
dcim_inventory_poller.py
(baca dari PostgreSQL, bukan dari BMC)
        ↓
Ralph CMDB
```

Tidak ada garis langsung dari dcim_inventory_poller.py ke BMC server.
Poller hanya membaca hasil Telegraf dari database.
```
