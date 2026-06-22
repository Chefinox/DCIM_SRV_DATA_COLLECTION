# Panduan Akses Data untuk Tim AI (L14 — Data Interface)

> **Versi**: 1.0 · **Tanggal**: 2026-06-17 · **Selaras**: `docs/architecture/v4.2-pipeline-architecture.md` §16
>
> **Prinsip**: Host `srv-rnd-dcim` (10.70.0.56) adalah **penyedia data**. Training & inference
> model AI dijalankan **di infrastruktur tim AI**, mengakses data ini **dari luar** lewat
> koneksi read-only. **Tidak ada** model/agen AI yang di-deploy di host ini.

---

## 1. Kredensial

Akun database khusus tim AI: **`dcim_ai_reader`** (read-only + write terbatas).

| Field | Nilai |
|---|---|
| Host | `10.70.0.56` |
| Port | `5432` |
| Database | `dcim_sot` |
| User | `dcim_ai_reader` |
| Password | lihat file rahasia di host: `configs/ai_reader.credentials` (tidak dimuat di repo) |

Connection string:
```
postgresql://dcim_ai_reader:<PASSWORD>@10.70.0.56:5432/dcim_sot
```

> Password dikirim terpisah lewat kanal aman. Jangan menaruhnya di kode/Git.

---

## 2. Hak Akses (least privilege)

| Objek | Akses | Kegunaan |
|---|---|---|
| `v_train_server`, `v_train_ups`, `v_train_nas`, `v_train_network`, `v_train_cctv`, `v_train_nvr` | **SELECT** | Fitur siap-latih (pivot per menit, wide) |
| `dcim_metrics_archive` | **SELECT** | Histori time-series mentah jangka panjang (format long) |
| `dcim_failure_events` | **SELECT** | Label kegagalan (supervised) |
| `unified_assets`, `dcim_server_{disks,ram,processors,nics}` | **SELECT** | Metadata & inventaris hardware |
| `dcim_server_anomalies` | **SELECT, INSERT, UPDATE** | **Wadah hasil** — tulis skor anomali ke sini |

**Tidak diberikan**: akses tulis ke `dcim_events`/`dcim_metrics_archive`/`dcim_failure_events`,
`CREATE`/`DROP`, `DELETE`, dan superuser. Batas koneksi: **10** sesi paralel.

---

## 3. Membaca data latih

```sql
-- Fitur server siap-latih (per menit)
SELECT ts, serial_number, hostname, temp_celsius, power_watts, fan_rpm, cpu_util_pct
FROM   v_train_server
WHERE  ts >= now() - interval '30 days'
ORDER  BY ts;

-- Histori mentah (long) bila butuh field di luar view pivot
SELECT event_time, device_type, hostname, field_key, field_value
FROM   dcim_metrics_archive
WHERE  device_type = 'server' AND event_time >= now() - interval '30 days';

-- Label kegagalan untuk supervised learning
SELECT * FROM dcim_failure_events ORDER BY event_time DESC;
```

> View `v_train_*` adalah **materialized view**, di-refresh harian (~03:00 WIB).
> Untuk data lebih segar, baca langsung `dcim_metrics_archive`.

---

## 4. Menulis hasil anomali

Tulis hasil scoring model ke `dcim_server_anomalies`:

```sql
INSERT INTO dcim_server_anomalies
  (event_time, hostname, serial_number,
   cpu_util_pct, mem_util_pct, net_rx, net_tx, temp_celsius, power_watts,
   anomaly, anomaly_score, model_version)
VALUES
  (now(), 'server-HCI-01', 'SN12345',
   42.5, 63.1, 1000, 2000, 51.2, 320,
   true, 0.97, 'isoforest-v1');
```

Kolom `id` (bigserial) terisi otomatis. Set `model_version` untuk menelusuri model mana
yang menghasilkan skor. Hanya `dcim_server_anomalies` yang boleh ditulis.

---

## 5. (Opsional) Stream real-time via Kafka

Bila butuh data real-time (bukan batch), subscribe ke Kafka **dari host tim AI**:

| Field | Nilai |
|---|---|
| Broker | `10.70.0.56:9092` |
| Topik | `dcim.enriched.events` (sudah ter-enrich metadata CMDB) |
| Consumer group | gunakan grup khusus tim AI, mis. `ai-team-inference` |

> Catatan: bila Kafka hanya listen di `localhost`, perlu koordinasi infra untuk membuka
> `advertised.listeners` / akses jaringan. Default integrasi adalah jalur **PostgreSQL**.

---

## 6. Reproduksi / rotasi role

DDL role tersimpan idempoten di `sql/ai_access_role.sql`. Untuk membuat ulang atau merotasi
password:

```bash
psql -v ai_pw="'<PASSWORD_BARU>'" -U sot_admin -d dcim_sot -f sql/ai_access_role.sql
# atau via container:
AIPW='<PASSWORD_BARU>'
docker exec -i dcim_sot_postgres psql -U sot_admin -d dcim_sot -v ai_pw="'$AIPW'" < sql/ai_access_role.sql
```
