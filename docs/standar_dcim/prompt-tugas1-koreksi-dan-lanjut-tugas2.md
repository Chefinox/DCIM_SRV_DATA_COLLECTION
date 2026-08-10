# Lanjutan — Koreksi Audit & Lampu Hijau untuk Tugas 2

Tabel audit Tugas 1 sudah saya verifikasi silang secara independen (5 baris paling kompleks dicek
ulang langsung ke kode: konfigurasi listener Kafka, field enrichment, skema tabel lineage,
concurrency control poller, dan observability metrics). Hasilnya solid — 3 dari 5 cocok persis.
Ada 2 hal di tabel Tugas 1 sendiri yang perlu dikoreksi dulu sebelum lanjut ke Tugas 2:

## Koreksi 1 — Baris #2 (Max concurrent / semaphore)

Klaim "Tidak ada concurrency control di kode poller manapun" terlalu general. Yang benar:

- **Telemetry connector poller** (`redfish_poller.py`, `redfish_telemetry_poller.py`,
  `mikrotik_poller.py`, `snmp_ups_poller.py`, `nas_poller.py`, `hikvision_poller_daemon.py`,
  `cctv_poller.py`, `ipmi_poller.py`) — benar, **tidak ada** `ThreadPoolExecutor`/`Semaphore`
  sama sekali. Klaim ini valid untuk kelompok ini (yang memang jadi scope §3.1/§3.2 PR #40).
- **Inventory sync poller** (`dcim_inventory_poller.py`, `nas_inventory_poller.py`) — ini
  kelompok berbeda (bulk/periodic inventory sync, bukan connector telemetry per-source), dan
  **memang punya** bounded concurrency: `ThreadPoolExecutor(max_workers=30)` dan
  `ThreadPoolExecutor(max_workers=6)`.

**Tindakan:** perbaiki kalimat di tabel audit menjadi eksplisit ruang lingkupnya — "Tidak ada
concurrency control pada *telemetry connector poller* (kelas yang didokumentasikan di §3.1).
Inventory sync poller (komponen terpisah, di luar scope §3.1) menggunakan `ThreadPoolExecutor`
dengan `max_workers` 6–30." Saat memperbaiki dokumen PR #40 di Tugas 2, pastikan §3.2 hanya
mengklaim untuk *connector class* yang memang dibahas di §3.1 — jangan campur dengan inventory
sync job.

## Koreksi 2 — Baris #17 (Observability / Connector Metrics)

Klaim "Aktual hanya `dcim_circuit_breaker_state` dan `dcim_circuit_breaker_last_change_timestamp`"
tidak lengkap. Ditemukan juga di `itop/sync/sync_netbox_to_itop.py`:
`netbox_itop_sync_objects_total` (Counter), `netbox_itop_sync_errors_total` (Counter),
`netbox_itop_sync_last_success_timestamp` (Gauge), `netbox_itop_sync_last_run_status` (Gauge).

**Tindakan:** sebelum menulis ulang §9.1/§9.2 di Tugas 2, jalankan pencarian menyeluruh untuk
custom Prometheus metric di seluruh repo (bukan cuma `circuit_breaker_monitor.py`):
```bash
grep -rln "prometheus_client\|# TYPE\|# HELP\|Gauge(\|Counter(\|Histogram(" --include="*.py" . \
  | grep -v "_archived\|.pyc"
```
Untuk setiap file yang muncul, catat metric name aktualnya. Perbaiki §9.1/§9.2 PR #40 supaya
daftar "metric yang sudah ada" mencerminkan **semua** metric custom yang benar-benar ter-export,
bukan cuma yang ditemukan dari satu file. Sisanya (nama metric yang diusulkan tapi belum ada)
tetap boleh masuk dokumen, **asalkan dilabel eksplisit "proposed / not yet implemented"**.

## Instruksi Umum untuk Sisa Tabel

Untuk baris-baris lain di tabel Tugas 1 yang tidak saya spot-check secara eksplisit di atas
(baris #1, #3, #4–8, #10–16, #18–21), saya tidak menemukan indikasi masalah dari sampling saya,
tapi tetap terapkan disiplin yang sama: setiap kali menuliskan ulang konten dokumen di Tugas 2,
sertakan referensi file:line sebagai komentar di commit message atau catatan kerja (tidak perlu
masuk ke isi dokumen final, karena dokumen untuk publik harus tetap generik) — supaya proses ini
tetap bisa diaudit ulang kalau ada pertanyaan lanjutan.

## Lampu Hijau

Setelah dua koreksi di atas diterapkan pada tabel audit, **lanjutkan ke Tugas 2**: tulis ulang
`docs/architecture/multi-source-ingestion-pipeline.md` berdasarkan tabel audit yang sudah
dikoreksi, commit ke branch `docs/actual-pipeline-architecture-reference` (branch PR #40 yang
sama), jalankan `make phase0-check` dan `check_public_repo_safety.py`, lalu push dan laporkan
hasilnya ke saya sebelum PR diminta review ulang oleh `shuffahaqgzz`.
