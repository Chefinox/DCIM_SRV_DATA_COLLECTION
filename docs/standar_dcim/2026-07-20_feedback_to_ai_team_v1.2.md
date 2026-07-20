# Feedback untuk Tim AI — Verifikasi Data Aktual vs API v1.2

> **Dari:** Fakhri (Tim DCIM Infra)
> **Tanggal:** 20 Juli 2026
> **Terkait:** Verifikasi API `http://192.168.100.35:8000/api/v1/docs` & data pipeline
> **Referensi:** [Feedback Syauqi v1.1](2026-07-20_feedback_for_syauqi_v1.1.md)

---

Setelah menindaklanjuti feedback Syauqi, kami melakukan pengecekan langsung terhadap endpoint API yang Tim AI deploy. Berikut temuan dari sisi pipeline DCIM.

---

## 🔴 Issue 1: `datacenter_id` = `dc-001` — Hardcoded, Bukan Data Aktual

### Temuan

API mengembalikan `"datacenter_id": "dc-001"`, namun field ini **tidak memiliki sumber data** di pipeline DCIM:

```
Pipeline DCIM End-to-End:
  Raw Kafka → Normalizer → Enriched Kafka → Analytics Bridge
    → dcim.analytics.metrics → Stream Processor → TimescaleDB
```

**Tidak ada satu pun layer** di pipeline yang memproduksi atau meneruskan `datacenter_id`:

| Layer | Ada `datacenter_id`? | Sumber |
|-------|:---:|--------|
| Raw Kafka (`dcim.raw.*`) | ❌ | — |
| Normalizer → `dcim.normalized.events` | ❌ | Hanya: `hostname`, `serial_number`, `ip`, `model`, `manufacturer` |
| Enrichment (NiFi + FastAPI) | ❌ | Menambah `ci_id`, `asset_id`, `site_id`, `rack_id` — bukan `datacenter_id` |
| Analytics Bridge → `dcim.analytics.metrics` | ❌ | Payload: `{timestamp, metric_name, ci_id, asset_id, device_type, metric_unit, payload, metadata}` |
| Stream Processor → TimescaleDB | ❌ | INSERT columns: `(time, metric_name, ci_id, asset_id, source, value, unit, tags)` |
| TimescaleDB `tags` JSONB keys | ❌ | Query `SELECT * WHERE tags ? 'datacenter_id'` → **0 rows** |

### Verifikasi Database

```sql
-- Semua tag keys yang ADA di TimescaleDB:
SELECT DISTINCT jsonb_object_keys(tags) FROM metrics
WHERE time > NOW() - INTERVAL '1 hour';

-- Hasil: hostname, serial_number, ip, model, manufacturer, device_type,
--        agent_host, bios_version, diskID, firmware, ifName, location, volumeName
-- TIDAK ADA: datacenter_id, site, datacenter, dc_id
```

### Rekomendasi

1. **Short-term**: Jika `datacenter_id` diperlukan, gunakan data dari **enrichment layer** — field `site_id` dan `rack_id` sudah tersedia di tabel `metrics` (kolom `ci_id`, `asset_id`). Tabel `unified_assets` di PostgreSQL `dcim_sot` memiliki relasi `asset → rack → datacenter`.
2. **Long-term**: Setelah CMDB (iTop/Ralph) lengkap, kita bisa menambahkan `datacenter_id` ke enrichment pipeline via NiFi → Avro → TimescaleDB.

---

## 🔴 Issue 2: PUE / Energy API — Unit & Formula Salah

### API Response yang Diterima

```json
{
  "datacenter_id": "dc-001",
  "pue": 10.54,
  "total_power_kw": 2862.34,
  "it_power_kw": 271.68,
  "cooling_power_kw": 2590.66,
  "cooling_efficiency": 0.1,
  "rating": "inefficient",
  "recommendations": [
    "URGENT: PUE > 2.0 indicates major inefficiency..."
  ],
  "carbon_intensity_kg_per_kwh": 0.85,
  "estimated_monthly_cost_usd": 206088.31,
  "calculated_at": "2026-07-20T08:16:05.026625"
}
```

### Data Aktual di TimescaleDB

```sql
-- 30 menit terakhir:
SELECT metric_name, AVG(value), MIN(value), MAX(value)
FROM metrics WHERE metric_name IN ('total_facility_power','it_equipment_power')
AND time > NOW() - INTERVAL '30 minutes'
GROUP BY metric_name;

-- Hasil:
-- total_facility_power  | avg=2871.4 | min=2700 | max=3000 | unit=watts
-- it_equipment_power    | avg=275.6  | min=243  | max=300  | unit=watts
```

### Masalah 1: Unit Confusion (watts vs kilowatts)

API mengasumsikan nilai TSDB sudah dalam **kilowatt**, padahal unit sebenarnya adalah **watt**:

| Metric | Actual TSDB (watts) | API Memperlakukan Sebagai | Seharusnya |
|--------|:---:|:---:|:---:|
| `total_facility_power` | ~2,871 W = **2.87 kW** | 2,862.34 kW | **Off by 1000×** |
| `it_equipment_power` | ~276 W = **0.28 kW** | 271.68 kW | **Off by 1000×** |

### Masalah 2: UPS Idle — Data Power Tidak Real

UPS (`UPS-FIT`) saat ini dalam kondisi **idle/bypass**:

```
output_load       = 0%
output_current_L1 = 0
output_current_L2 = 0
output_current_L3 = 0
```

Nilai `total_facility_power` dan `it_equipment_power` dihasilkan dari **rumus estimasi fallback**, bukan dari pembacaan beban aktual. UPS 30KVA tidak sedang menanggung beban IT saat ini.

### Masalah 3: PUE Tidak Masuk Akal

```
PUE API        = 2862.34 / 271.68 = 10.54  ← absurd, normal PUE = 1.1–1.5
Cooling API    = 2862.34 - 271.68 = 2,590 kW  ← lebih besar dari IT load
```

PUE 10.54 hanya terjadi jika cooling mengkonsumsi 10× IT power, yang secara fisik tidak mungkin di data center kecil ini.

### Rekomendasi

1. **Unit fix**: Bagi nilai watt dengan 1000 sebelum menghitung PUE.
2. **Load gate**: Hanya hitung PUE jika `output_load > 0`. Jika `output_load = 0`, return `null` atau flag `"ups_idle": true`.
3. **Fallback metrics**: Gunakan `battery_capacity`, `output_voltage`, `battery_temperature` — metric ini akurat meskipun UPS idle. Bisa digunakan untuk anomaly detection sementara.

---

## 🟡 Kondisi UPS Saat Ini — Konteks untuk Tim AI

| Status UPS | Detail |
|------------|--------|
| Device | UPS-FIT (APC Smart-UPS 30KVA) |
| Output Load | **0%** (idle/bypass — tidak menanggung beban) |
| Battery | 100%, runtime 237 sec, voltage 268V |
| Output | 231V, 49.9Hz |
| **Power data valid?** | ❌ — nilai hasil estimasi, bukan pengukuran aktual |

### Metric UPS yang AKURAT (bisa dipakai sekarang)

| Metric | Nilai | Bisa Untuk |
|--------|-------|------------|
| `battery_capacity` | 100% | Health monitoring |
| `battery_temperature` | 0°C (sensor mungkin tidak aktif) | Anomaly detection |
| `battery_voltage` | 268V | Trend analysis |
| `output_voltage` | 231V | Stability monitoring |
| `output_frequency` | 49.9Hz | Grid quality |

### Metric UPS yang TIDAK AKURAT (jangan dipakai dulu)

| Metric | Masalah |
|--------|---------|
| `total_facility_power` | Estimasi dari rumus fallback, bukan data aktual |
| `it_equipment_power` | Estimasi dari rumus fallback, bukan data aktual |
| `output_load` | 0% — tidak ada beban |

---

## ✅ Perbaikan Pipeline (Sudah Dilakukan)

| Perbaikan | Status |
|-----------|:---:|
| Metric gap: 5→25 metric types | ✅ |
| `memory_utilization` server (field name fix) | ✅ |
| `total_facility_power` + `it_equipment_power` | ✅ (tapi UPS idle) |
| Secondary metrics untuk semua device types | ✅ |

---

## 📋 Action Items

### Tim AI (Syauqi)

1. [ ] **Fix unit**: Bagi `total_facility_power` & `it_equipment_power` dengan 1000 (watt → kW) di API.
2. [ ] **Load gate**: Skip kalkulasi PUE jika `output_load = 0`. Return `null` atau `ups_idle: true`.
3. [ ] **Data source**: Ganti `datacenter_id` hardcoded `"dc-001"` dengan lookup dari tabel `unified_assets` di PostgreSQL `dcim_sot` (kolom `ci_id`/`asset_id` sudah tersedia di TimescaleDB).
4. [ ] **Priority shift**: Fokus anomaly detection dulu dengan metric akurat (battery, voltage, temperature, CPU, memory). Energy optimization tunda sampai UPS online dengan beban.

### Tim Infra (Fakhri)

1. [ ] **Menambahkan `datacenter_id` ke pipeline** — enrichment layer sudah punya `site_id`/`rack_id`, bisa diperluas ke `datacenter_id` setelah CMDB lengkap.
2. [ ] **Monitoring UPS status** — alert jika UPS tetap idle > 24 jam (mungkin wiring issue).

---

## Quick Reference — Query Data Aktual

```sql
-- Cek apakah UPS punya load (harus > 0 untuk PUE valid)
SELECT time, value FROM metrics 
WHERE metric_name = 'output_load' AND source = 'ups'
ORDER BY time DESC LIMIT 1;

-- Cek semua power metrics terbaru
SELECT metric_name, value, unit, time FROM metrics 
WHERE metric_name IN ('total_facility_power','it_equipment_power')
ORDER BY time DESC LIMIT 5;

-- Cek semua tag keys yang tersedia
SELECT DISTINCT jsonb_object_keys(tags) FROM metrics 
WHERE time > NOW() - INTERVAL '1 hour';
```

---

*Siap didiskusikan lebih lanjut. Pipeline siap untuk anomaly detection real-time — energy optimization menunggu UPS online.*
