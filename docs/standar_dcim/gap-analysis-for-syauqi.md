# Gap Analysis — Dokumentasi Syauqi vs Kebutuhan API Analytics

> **Untuk:** Syauqi (Tim AI)
> **Dari:** Fakhri (Tim DCIM Infra)
> **Tanggal:** 15 Juli 2026
> **Tujuan:** Melengkapi dokumentasi pipeline agar Tim AI bisa deploy dan menjalankan API Analytics dengan sempurna

---

## Ringkasan

Dokumentasi Syauqi (`ai-pipeline-architecture.md`, `ai-team-access.md`, `README.md`) **sudah sangat baik** untuk sisi pipeline ingestion. Namun, ada gap besar di sisi **tabel-tabel hasil analytics** yang dibutuhkan oleh API Block 7. Akibatnya, begitu Tim AI deploy API, endpoint seperti Anomalies dan Predictions mengembalikan array kosong — bukan karena pipeline nggak jalan, tapi karena tabelnya belum dibuat.

---

## Yang Sudah Benar di Dokumen Syauqi

| Item | Status | Keterangan |
|------|--------|------------|
| Koneksi TimescaleDB (`10.70.0.56:5433`, `dcim_analytics`) | ✅ | Sudah lengkap |
| Credentials `ai_team` / `ai_team_access_pass` | ✅ | Sudah lengkap |
| Skema tabel `metrics` (hypertable, 8 kolom) | ✅ | Sudah lengkap |
| Continuous aggregates (`metrics_hourly`, `metrics_daily`) | ✅ | Sudah lengkap |
| Kafka topics + SSL config | ✅ | Sudah lengkap |
| WARNING soal localhost vs `10.70.0.56` | ✅ | Sangat penting, sudah ada |
| Contoh query Python + SQL | ✅ | Sudah lengkap |
| RBAC roles: `ai_team`, `analytics_read`, `analytics_write` | ⚠️ | Ada, tapi tidak akurat (lihat di bawah) |

---

## Yang BELUM ADA di Dokumen Syauqi — Ini Harus Ditambahkan

### 1. Tabel-Tabel Hasil Analytics Tidak Didokumentasikan

Di `ai-pipeline-architecture.md` section "5. Analytics Layer" hanya menyebut 3 tabel:

```
metrics          → raw hypertable
metrics_hourly   → hourly continuous aggregate
metrics_daily    → daily continuous aggregate
```

**Ini hanya tabel INPUT (raw data).** API Block 7 juga butuh tabel-tabel OUTPUT berikut:

| Tabel | Fungsi | Digunakan oleh Endpoint |
|-------|--------|------------------------|
| `anomaly_events` | Menyimpan hasil deteksi anomali (Z-score) | `GET /anomalies`, `POST /anomalies/detect` |
| `predictions` | Menyimpan hasil prediksi kegagalan (IF/LOF/OCSVM ensemble) | `GET /predictions`, `POST /predictions/forecast` |
| `rca_reports` | Menyimpan laporan Root Cause Analysis | `POST /rca/analyze`, `GET /rca/{id}` |
| `capacity_forecasts` | Menyimpan hasil forecasting kapasitas | `POST /capacity/forecast` |
| `energy_reports` | Menyimpan laporan optimasi energi (PUE, cooling, dll) | `GET /energy`, `POST /energy/optimize` |
| `ml_models` | Registri model ML (versi, metrik, artifact path) | `GET /models`, `POST /models/register` |
| `model_drift_tracking` | Monitoring drift model ML | Internal |
| `audit_log` | Audit trail semua operasi analytics | Internal |

### 2. RBAC `ai_team` di Dokumen Tidak Akurat

Di `ai-team-access.md` baris 248:

```
| `ai_team` | SELECT on metrics, metrics_hourly, metrics_daily |
```

**Ini tidak cukup.** API analytics butuh:

- **SELECT** di semua tabel analytics (bukan cuma 3 tabel metrics)
- **INSERT** di `anomaly_events`, `predictions`, `rca_reports`, `capacity_forecasts`, `energy_reports`
- **UPDATE** di `anomaly_events` (untuk acknowledge/resolve anomaly)

Role yang benar (sesuai migration SQL `002_create_analytics_tables.sql`):

```
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ai_team;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ai_team;
```

### 3. Prosedur Migration SQL Tidak Disebutkan

Tabel-tabel analytics tidak otomatis terbuat. Harus dijalankan oleh **`analytics_user`** (schema owner) karena `ai_team` tidak punya permission `CREATE TABLE`. File migration:

```
/home/infra/dcim_project/implementation/dcim_ai_v2_rag/migrations/
├── 001_create_timescaledb_schema.sql   → sudah jalan (metrics + aggregates ada)
└── 002_create_analytics_tables.sql     → BELUM DIJALANKAN ⚠️
```

### 4. Column Mismatch di Tabel `predictions`

Di migration SQL, tabel `predictions` kolomnya:

| Migration Column | API Query Expects |
|-----------------|-------------------|
| `predicted_at` | `timestamp` |
| `risk_level` | `severity` |
| `recommended_actions` (JSONB array) | `recommendation` (text) |
| `contributing_factors` (JSONB array) | `contributing_factors` (JSONB array) |

⚠️ Backend API perlu di-patch agar sesuai dengan migration schema.

### 5. Data Flow Analytics Result Tidak Didokumentasikan

Dokumen hanya menunjukkan flow sampai ke TimescaleDB metrics:

```
Sources → NiFi → Kafka → TimescaleDB (metrics)
```

Tidak ada dokumentasi tentang apa yang terjadi setelah itu:

```
TimescaleDB (metrics) → API analytics → anomaly_events / predictions / rca_reports / ...
                                              ↓
                                         Tim AI consume hasil
```

---

## Action Items untuk Syauqi

### Wajib (segera)

- [ ] **Tambahkan dokumentasi 6+ tabel analytics** di `ai-pipeline-architecture.md` section 5
- [ ] **Update RBAC `ai_team`** di `ai-team-access.md` — tambahkan INSERT/UPDATE, sebutkan semua tabel
- [ ] **Dokumentasikan prosedur migration** — siapa yang jalanin (`analytics_user`), file mana, cara verifikasi
- [ ] **Sertakan dependency tabel analytics** di dokumentasi onboarding Tim AI — sebelum deploy API, pastikan migration sudah jalan

### Disarankan

- [ ] Tambahkan **data flow analytics result** di diagram arsitektur
- [ ] Buat **checklist verifikasi** untuk Tim AI sebelum deploy API:
  1. `SELECT COUNT(*) FROM anomaly_events` → harus return angka (bukan error)
  2. `SELECT COUNT(*) FROM predictions` → harus return angka (bukan error)
  3. `SELECT COUNT(*) FROM metrics` → harus > 0
- [ ] Tambahkan **troubleshooting section** untuk kasus "API return array kosong" — cek apakah tabel analytics sudah ada

---

## Catatan Tambahan

Backend API akan di-patch oleh Tim DCIM untuk:
- Fix silent error handling (ganti `return []` jadi raise exception yang jelas)
- Fix column mismatch di `predictions.py`
- Bikin script verifikasi otomatis bahwa semua tabel analytics sudah ada

Begitu patch selesai, API akan memberikan error message yang jelas jika tabel belum dibuat — bukan `[]` yang membingungkan.

---

## Referensi

| File | Path |
|------|------|
| Migration SQL (001) | `/home/infra/dcim_project/implementation/dcim_ai_v2_rag/migrations/001_create_timescaledb_schema.sql` |
| Migration SQL (002) | `/home/infra/dcim_project/implementation/dcim_ai_v2_rag/migrations/002_create_analytics_tables.sql` |
| Migration Runner | `/home/infra/dcim_project/implementation/dcim_ai_v2_rag/migrations/run_migrations.py` |
| API Config | `/home/infra/dcim_project/implementation/dcim_ai_v2_rag/api/config.py` |
| DBA Handoff Doc | `/home/infra/dcim_project/implementation/dcim_ai_v2_rag/docs/DBA_HANDOFF.md` |
| Gap Closure Plan | `/home/infra/dcim_project/task/2026-07-15_block7_gap_closure_plan.md` |
