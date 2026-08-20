# Prompt untuk Agent: Hardening Terakhir + Konsolidasi Status Final untuk Task Tracker

## Konteks

Ini task penutup dari rangkaian panjang investigasi & remediasi pipeline DCIM (SIEM ingestion, Kafka quorum, Vault credential remediation, AppRole per-connector, token caching). Dua item teknis kecil masih tersisa dari review terakhir, dan owner butuh **satu ringkasan status final yang bisa langsung dipakai untuk mengisi task tracker** — bukan cuma laporan naratif lagi, tapi tabel status per item yang jelas Done/Blocked/Pending dengan bukti dan link commit.

## Batasan Keras (Do Not)

- **JANGAN tandai item manapun "Done" di ringkasan final tanpa bukti yang sudah diverifikasi di laporan-laporan sebelumnya atau di task ini** — kalau statusnya masih Blocked/Pending (mis. RouteOnContent NiFi yang masih menunggu eksekusi GUI owner, migrasi `redfish_poller.py`/`server_inventory_collector.py` ke `secrets.py`, revoke root token yang masih ditahan), tulis apa adanya.
- **JANGAN ubah/redesign apapun di luar dua item hardening kecil yang diminta** — task ini bukan kesempatan untuk merombak ulang AppRole/caching yang sudah diverifikasi selesai.

## Tugas 1 — Chmod Restrictive untuk File Cache Token

1. Di `src/utils/secrets.py`, tambahkan `os.chmod(cache_file, 0o600)` tepat setelah token berhasil ditulis ke file cache di `_store_cached_token()` — pastikan hanya owner proses yang bisa baca/tulis file itu.
2. Uji: buat token baru, cek permission file hasil (`stat -c "%a" vault/config/cache/token_<connector>.json` harus menunjukkan `600`).
3. Pastikan directory `vault/config/cache/` sendiri juga permission-nya wajar (tidak world-readable) — kalau perlu, tambahkan `os.chmod` untuk directory juga saat `_cache_dir()` membuatnya (`0o700`).

## Tugas 2 — Validasi `VAULT_CONFIG_DIR` (Cegah Silent Failure)

1. Saat ini kalau `VAULT_CONFIG_DIR` tidak di-set dan default path (`/home/infra/dcim_metrics_project/vault/config`) tidak ada/salah di suatu environment, caching akan diam-diam gagal (selalu fresh login tanpa error jelas) — user/operator tidak akan tahu caching sebenarnya tidak aktif.
2. Tambahkan log warning eksplisit (level `WARNING`, bukan `debug`) saat `_cache_dir()` dipanggil dan ternyata base directory tidak ada / tidak bisa dibuat — supaya kegagalan caching terlihat di log, bukan silent.
3. Uji dengan sengaja set `VAULT_CONFIG_DIR` ke path yang tidak valid, konfirmasi warning muncul di log dan kode tetap fallback aman ke fresh login (tidak crash).

## Tugas 3 — Konsolidasi Status Final Seluruh Rangkaian Task (untuk Task Tracker Owner)

Review ulang **seluruh** laporan handoff yang sudah dibuat sepanjang rangkaian investigasi ini (dari audit SIEM/Jolt pertama sampai token caching fix terakhir), dan susun **satu tabel status final** yang mencakup setiap task/sub-task dengan kolom:

| Kolom | Isi |
|---|---|
| Task/Item | Nama singkat |
| Terkait Sub-task Awal | ST-391/392/393/394 atau item remediasi keamanan |
| Status Final | Done / Blocked / Pending / Out-of-Scope |
| Bukti | Commit hash / link laporan handoff yang relevan |
| Catatan | Kalau Blocked/Pending, apa yang masih ditunggu |

Cakupan minimal yang harus masuk tabel (cross-check ke laporan-laporan sebelumnya, jangan asal tulis dari ingatan):

1. **SIEM Ingestion — RouteOnContent fix** (status terakhir: menunggu eksekusi GUI owner — cek apakah sudah dieksekusi sejak laporan terakhir, jangan asumsikan masih sama).
2. **DLQ Writer fix** (`sys.excepthook` di 4 poller — status: Partially Fixed, ada gap threading/error-isolation di `mikrotik_poller.py` & `cctv_poller.py`).
3. **Kafka KRaft Quorum** (status: Healthy, dipulihkan dari `kafka3` down).
4. **Load Test ST-394** (status: Pass, hasil run terakhir).
5. **Mock API Adapters ST-391/392** (status: Healthy).
6. **S3/MinIO Cold Storage ST-393** (status: On-Hold, tidak berubah — cukup dikonfirmasi ulang statusnya konsisten di tracker).
7. **Vault credential leak remediation** (git history cleanup, redaksi token/password — status: Done, terverifikasi independen).
8. **Root token regeneration & revoke** (status terakhir: token baru aktif, revoke ditahan sampai AppRole siap — cek apakah sudah waktunya direvoke sekarang bahwa AppRole per-connector sudah selesai & teruji; kalau ya, catat sebagai **item terbuka yang butuh keputusan owner**, bukan dieksekusi sendiri di task ini).
9. **Vault lease cleanup (289K)** (status: Done, root cause AppRole `dcim-role` TTL=0 sudah diperbaiki).
10. **AppRole per-connector implementation** (status: Done, 4 AppRole scoped + policy HCL as code).
11. **Token caching fix** (status: Done setelah task ini + Tugas 1-2 di atas selesai).
12. **Migrasi `redfish_poller.py`/`server_inventory_collector.py` ke `secrets.py`** (status: Pending, belum dikerjakan).
13. **Migrasi credential ES ke Vault penuh** (status: cek laporan — sempat blocked karena token invalid, apakah sudah bisa dilanjutkan sekarang dengan token baru yang valid, atau masih pending karena belum ada izin eksplisit owner untuk task itu).
14. **Deprecate `dcim-role` lama** (status: Pending, ditahan sampai semua connector stabil di AppRole baru).

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-final-hardening-and-status-consolidation.md`:

1. **Bukti Tugas 1 & 2** — diff kode, hasil test permission file, hasil test warning log.
2. **Tabel Status Final Konsolidasi** (Tugas 3) — tabel lengkap seperti struktur di atas, ini bagian yang akan langsung dipakai owner untuk isi task tracker-nya.
3. **Daftar Item yang Butuh Keputusan/Aksi Owner** — ringkas terpisah dari tabel, cuma item yang statusnya Blocked/Pending dan actionable, diurutkan prioritas.
