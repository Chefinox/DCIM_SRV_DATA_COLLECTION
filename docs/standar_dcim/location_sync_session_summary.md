# SESSION SUMMARY DOCUMENT

## 1. Session Metadata
- **Session Title:** Fixing Hardcoded Locations & iTop Rack Sync Root Cause
- **Date/Time:** 2026-06-05
- **User:** infra
- **Main Topic:** Data Pipeline Location Synchronization & iTop Consumer Debugging
- **Session Type:** Debugging / Coding / Review
- **Current Status:** Needs Follow-up (Menunggu persetujuan user untuk fix Root Cause)

---

## 2. High-Level Summary
Sesi ini difokuskan untuk menyelesaikan masalah *hardcode* lokasi/rak pada pipeline sinkronisasi iTop. Pekerjaan dimulai dengan mengganti default site/rack yang kosong menjadi "Unknown" dan membersihkan *hardcode* mapping rack di inventory poller. Setelah itu, dilakukan investigasi mendalam terkait masalah lokasi rak di iTop yang tidak tersinkronisasi (*real-time*) dengan data dari Ralph (contoh: SRV-Render-01/02). Investigasi berhasil menemukan 3 *root cause* utama, dan analisis detail telah disajikan dalam bentuk Artifact tanpa mengubah kode *consumer* karena user ingin me-*review* detail masalahnya terlebih dahulu.

---

## 3. User Goal
- **Primary Goal:** Menghapus *hardcode* site/rack di seluruh *pipeline* dan memastikan iTop tersinkronisasi otomatis dengan perubahan lokasi/rak yang terjadi di Ralph (Source of Truth).
- **Secondary Goals:**
  - Default untuk lokasi/rak yang tidak ditemukan di-set ke `"Unknown"`, bukan *empty string* `""`.
  - Mencegah timbulnya duplikasi *rack* di iTop ketika terjadi perpindahan ruangan.
- **Expected Output:** Analisis masalah sinkronisasi lokasi server (SRV-Render) di iTop dan skrip *pipeline* yang dinamis tanpa data statis.
- **Success Criteria:** *Root cause* kegagalan update lokasi ditemukan dan dapat dipahami, tidak ada duplikat *rack* yang tercipta di iTop.

---

## 4. Important Context
- **Background:** Pipeline data DCIM (Poller -> Kafka -> Normalizer -> Enrichment -> iTop Consumer) mengalami kegagalan pada pembaruan data *site* dan *rack* di iTop walau SoT di Ralph sudah diperbarui. Duplikasi *rack* juga terjadi.
- **Current Environment:** OS Linux, Database PostgreSQL (`unified_assets` sebagai referensi fallback), Kafka (`dcim.normalized.events`, `dcim.metrics.enriched.v2`).
- **Known Constraints:** Penggantian *consumer topic* di `dcim_itop_unified_consumer.py` berisiko tinggi merusak / *reset offset* *pipeline* Kafka saat ini yang sedang live.
- **User Preferences:** User ingin melihat analisis detail (*Root Cause Analysis*) sebelum AI mengimplementasikan *fix* ke kode produksi (*"Jangan di fix dulu aku ingin tahu detailnya"*).

---

## 5. Key Decisions Made

| Decision | Reason | Impact |
|---|---|---|
| Fallback kosong diubah ke `"Unknown"` | User tidak ingin site dibiarkan *empty string* `""`. | Kolom *site* dan *rack* di kode consumer dan poller diisi `"Unknown"` bila tidak tersedia. |
| Menghapus *manual rack mapping* di poller | Mencegah penimpaan data SoT yang dinamis dari Ralph oleh nilai statis bawaan skrip. | Semua lokasi/rak bergantung murni pada data dari DB/Ralph. |
| Memodifikasi logika `get_or_create_rack` di iTop | Sebelumnya membuat duplikat rack jika lokasinya berbeda. Kini diubah menjadi *update* `location_id` rack jika ditemukan nama sama. | Duplikasi Rack di iTop teratasi. Rack pindah lokasi otomatis secara *real-time*. |
| *Revert* penerapan fix lokasi server | User menginstruksikan untuk tidak langsung memperbaiki masalah SRV-Render sebelum tahu penyebabnya. | Pipeline tidak berubah, menunggu persetujuan fix dari user setelah membaca *Root Cause Artifact*. |

---

## 6. Work Completed
- [x] Refactoring site fallback menjadi `"Unknown"` pada `dcim_sql_consumer.py`, `dcim_inventory_poller.py`, dan `executor.py`.
- [x] Penghapusan *hardcode* penamaan rak statis pada `dcim_inventory_poller.py` (contoh: Rack Server 1/2, Wall Mount CCTV).
- [x] Perbaikan fungsi `get_or_create_rack` di `dcim_itop_unified_consumer.py` untuk mengakhiri duplikasi *Rack*.
- [x] Investigasi dan analisis kegagalan pembaruan lokasi Server (seperti masalah SRV-Render-01/02).
- [x] Pembuatan *Artifact* `rack_location_root_cause.md` yang merinci 3 *root cause* dan memberikan opsi solusi.

---

## 7. Current Progress / State

~~~text
Current state:
Proses perbaikan dan refactoring poller/rack duplikat telah tuntas. Pekerjaan debugging gagalnya update lokasi (SRV-Render) selesai dengan 3 root cause teridentifikasi, namun implementasi solusi masih tertunda (di-revert / paused). Posisi terakhir adalah menunggu feedback/keputusan dari user terkait Rekomendasi Opsi Solusi yang ada di dalam artifact `rack_location_root_cause.md`. Selain itu, Server telah ter-restart sehingga sesi subagent/background service terhenti secara internal.
~~~

---

## 8. Open Issues / Unresolved Questions

| Issue / Question | Status | Recommended Action |
|---|---|---|
| iTop Consumer baca dari topik Kafka yang salah (tidak diperkaya *site/rack*) | Open | Aktifkan kembali fungsi *location fallback* dari DB `unified_assets` di consumer (Opsi A pada Artifact). |
| Data lokasi *Server* (SRV-Render) di iTop belum ter-update dengan Ralph | Open | Implementasikan Opsi A setelah disetujui user. |
| FIT-Core-SW *update loop* | Pending | *Throttle* caching atau modifikasi validasi *update* SNMP Memory/U. |

---

## 9. Next Recommended Actions
1. Review Artifact `rack_location_root_cause.md`.
2. Diskusikan dan setujui opsi perbaikan untuk masalah sinkronisasi lokasi (Rekomendasi: Terapkan **Opsi A**, yaitu mengembalikan *fallback lookup location* DB ke consumer).
3. Setelah disetujui, AI akan mengimplementasikan perbaikan di `dcim_itop_unified_consumer.py`.
4. Restart layanan `dcim-itop-unified.service` untuk melihat efeknya pada pemindahan lokasi server di iTop.
5. (Opsional) Lakukan optimasi terkait masalah update looping pada *Network Device* (contoh: `FIT-Core-SW`).

---

## 10. Files, Links, Artifacts, and References

| Item | Type | Purpose | Status |
|---|---|---|---|
| `scripts/dcim_inventory_poller.py` | File | Script Poller inventory hardware | Used / Updated |
| `scripts/dcim_itop_unified_consumer.py` | File | Kafka consumer yang menulis ke iTop | Used / Pending Fix |
| `rack_location_root_cause.md` | Artifact | Menjelaskan *root cause* & opsi solusi | Need Review |

---

## 11. Technical Details

### Architecture / Structure
~~~text
Masalah arsitektural yang ditemukan:
Telegraf -> dcim.metrics.raw -> Enrichment Service -> dcim.metrics.enriched.v2 (berisi site/rack).
Masalahnya: iTop Consumer justru membaca dari `dcim.normalized.events`.
Dampak: `raw_tags["site"]` pada consumer iTop menjadi selalu kosong, dan update lokasi gagal terjadi.
~~~

### Errors / Logs
~~~text
Consumer iTop saat ini mengalami update looping pada perangkat tertentu tanpa alasan operasional yang jelas:
[INFO] ↺ Updating NetworkDevice 'FIT-Core-SW' (ID=3002): ['networkdevicetype_id', 'nb_u']
Kejadian ini berulang setiap detik akibat Telegraf mengirim metrics dan memicu consumer.
~~~

---

## 12. User Preferences and Working Style
- **Tone Preference:** Profesional, berbasis bukti (*evidence-based*), informatif.
- **Detail Level:** Sangat detail. Mengharuskan AI memberikan analisis *Root Cause* yang komprehensif alih-alih langsung menambal kode.
- **Output Format Preference:** Terstruktur dan tidak memaksakan implementasi (*don't jump to code*).
- **Important Style Notes:** User ingin agar konfigurasi eksisting sebisa mungkin tidak diubah jika berisiko konflik (*prefer workaround* via kode / *Opsi A*). User harus meninjau penjelasan teknis secara mandiri.

---

## 13. Assumptions and Boundaries

### Confirmed Facts
- File *Poller* sekarang telah bebas dari *hardcoded* rack/site.
- Masalah duplikasi *Rack* saat perangkat dipindahkan di iTop telah diperbaiki secara permanen.
- iTop Consumer gagal memperbarui lokasi akibat hilangnya *fallback block* saat refactoring sebelumnya dan pembacaan *Kafka topic* yang keliru.

### Assumptions
- Kondisi *Update Loop* `FIT-Core-SW` membebani API iTop namun secara data tidak mendestruksi/merusak sistem.

### Do Not Assume
- Agent selanjutnya **Dilarang keras** mengaplikasikan *fix* kode pada `dcim_itop_unified_consumer.py` terkait masalah lokasi sebelum memperoleh instruksi spesifik persetujuan dari user untuk Opsi perbaikan tertentu.

---

## 14. Memory Candidates

| Memory Candidate | Reason |
|---|---|
| iTop Consumer membaca `dcim.normalized.events`, yang TIDAK memiliki tags *site* dan *rack*. | Fundamental pemahaman arsitektur *data ingestion* pada proyek ini untuk keperluan *debugging* lanjutan. |

---

## 15. Final Handoff Brief

~~~markdown
The previous session focused on membersihkan hardcode lokasi/rak di pipeline data ingestion dan men-debug isu kegagalan sinkronisasi perpindahan lokasi (contoh: SRV-Render-01/02) di iTop. The user wanted untuk mengetahui analisis detail terlebih dahulu (*root cause*) sebelum melakukan perbaikan. We completed refactoring `dcim_inventory_poller.py` agar "Unknown" menjadi default, memperbaiki fungsi pencegah duplikasi *Rack* secara *real-time* di iTop Consumer, dan membuat *Root Cause Artifact*. The current state is tertunda/paused, menanti review user atas Root Cause Artifact tersebut. The next agent should continue by mendiskusikan *feedback* user mengenai Opsi Fix pada artifact (Rekomendasi Opsi A) lalu mengimplementasikannya setelah disetujui. Important constraints/preferences: Jangan mengeksekusi fix kode yang mengubah *behavior* pipeline sinkronisasi lokasi sebelum mendapatkan instruksi eksplisit dari user.
~~~
