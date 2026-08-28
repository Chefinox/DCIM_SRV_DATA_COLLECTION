# Prompt untuk Agent: Implementasi AppRole Scoped Per-Connector di Vault (Sesuai Konvensi `dcim-wiki`)

## Konteks

Root token baru yang di-generate di task sebelumnya **masih aktif** (belum di-revoke — dan memang sengaja ditahan sampai AppRole pengganti siap, sesuai urutan yang sudah disepakati). Task ini fokus membangun AppRole scoped sebagai pengganti ketergantungan pada root token, sebelum root token itu boleh di-revoke di task berikutnya.

**Catatan dari owner:** owner sendiri **tidak ingat status akses Vault saat ini** dan mengira **belum ada Vault UI** yang aktif. Jangan asumsikan owner bisa membantu memberi akses — agent harus mendiagnosis sendiri apa yang tersedia di awal task (Tugas 0), baru lanjut.

Temuan dari `dcim-wiki` yang **wajib jadi acuan desain**:
- `product-description/dcim-core-platform-product-description.md`: prinsip **"Service account per connector dengan izin minimum"** — artinya AppRole idealnya dipisah per connector, bukan satu role generik dipakai bareng semua service seperti `dcim-role` saat ini.
- `technical-requirements/v4.2-goal-prompt.md`: konvensi project eksplisit menyebut **"Stop if: Vault setup memerlukan root token atau unseal key yang tidak bisa di-rollback"** — jadi operasi Vault yang sifatnya ireversibel harus membuat agent berhenti dan lapor ke owner, bukan lanjut otomatis, kecuali langkahnya memang bisa dipastikan aman/reversible.

## Batasan Keras (Do Not)

- **JANGAN asumsikan kamu punya akses admin Vault** — verifikasi dulu di Tugas 0, jangan langsung coba command yang butuh privilege tinggi.
- **JANGAN revoke root token yang sedang aktif** di task ini — itu scope task terpisah setelah AppRole ini diverifikasi berfungsi.
- **JANGAN buat AppRole baru dengan `token_ttl=0`/`token_max_ttl=0`** — ini root cause masalah 289K lease sebelumnya, jangan diulang.
- **JANGAN tulis nilai root_id/secret_id/token apapun di file yang ter-commit ke git** — gunakan `.gitignore` yang sudah ada (`vault/config/init.txt`, `role_id`, `secret_id`) sebagai pola, tambahkan entry baru ke situ kalau perlu file baru.
- **JANGAN buat satu AppRole generik untuk semua connector** — ikuti prinsip "per connector" dari wiki, kecuali kamu temukan alasan teknis kuat untuk menggabungkan beberapa connector (jelaskan alasannya di laporan kalau begitu).
- **Kalau di tengah jalan kamu menemukan operasi yang sifatnya ireversibel dan belum jelas cara rollback-nya** (di luar yang sudah dianalisis di prompt ini) — **STOP, laporkan ke owner, jangan lanjut eksekusi sendiri.** Ini konvensi resmi project, bukan sekadar saran.

## Tugas 0 (WAJIB PERTAMA) — Diagnosis Akses Vault Saat Ini

1. Cek apakah container/service Vault masih berjalan (`docker ps | grep vault`), dan cek statusnya (`vault status` — initialized/sealed/HA).
2. Cek apakah ada credential tersimpan lokal di host `srv-rnd-dcim` dari pekerjaan sebelumnya:
   - `vault/config/init.txt` (kemungkinan berisi root token baru hasil generate-root sebelumnya, dan/atau unseal key).
   - `vault/config/role_id`, `vault/config/secret_id` (kalau AppRole `dcim-role` lama masih dipakai referensinya).
3. Cek apakah ada **Vault UI** aktif di port default `8200` (`curl -s http://127.0.0.1:8200/ui/` atau cek dari luar host kalau expose ke network) — konfirmasi ke owner apakah dugaan "belum ada Vault UI" itu benar atau ternyata sudah aktif tapi belum pernah diakses. UI Vault (kalau aktif) hanya alat visual, bukan prasyarat — semua langkah di task ini tetap bisa dikerjakan lewat CLI/API tanpa UI.
4. Kalau ditemukan root token yang masih valid dari task sebelumnya (`vault token lookup`), itu yang dipakai untuk provisioning AppRole baru di task ini — **bukan** mencari/membuat token admin baru lagi.
5. Kalau ternyata **tidak ada akses admin sama sekali** (root token expired/hilang, tidak ada unseal key tersimpan) — **STOP di sini**, laporkan temuan ke owner dengan jelas apa yang hilang, dan jangan mencoba generate-root baru sendiri tanpa konfirmasi eksplisit owner (karena ini masuk kategori operasi sensitif yang sebelumnya butuh izin eksplisit juga).

## Tugas 1 — Baca Ulang Konvensi `dcim-wiki` yang Relevan (Konfirmasi, Bukan Investigasi dari Nol)

`dcim-wiki` sudah ter-pull di host `srv-rnd-dcim`. Baca ulang untuk konfirmasi sebelum desain:
1. `concepts/secret-management-strategy.md` dan `entities/vault.md` — prinsip umum (KV engine untuk static secret, audit semua akses, dynamic credentials di mana relevan).
2. `product-description/dcim-core-platform-product-description.md` bagian Security Specification — konfirmasi ulang prinsip "service account per connector dengan izin minimum".
3. Cek apakah ada update terbaru di wiki sejak terakhir dibaca (kemungkinan ada dokumen baru soal AppRole/TTL yang belum ada saat pengecekan terakhir) — kalau ada detail baru yang lebih spesifik, ikuti itu.

## Tugas 2 — Inventarisasi Connector yang Butuh AppRole Terpisah

1. Daftar semua service/script yang saat ini mengakses Vault (baik langsung maupun lewat `dcim-role` yang sudah ada): poller virtualization (`proxmox_fixture_adapter.py` / `virtualization_poller_nifi.py`), ITSM connector (`servicenow.py`, `jira.py`), Telegraf consumer (untuk credential ES), dan komponen lain kalau ditemukan.
2. Untuk tiap connector, identifikasi **path secret spesifik** yang benar-benar dia butuhkan (bukan akses luas) — ini jadi dasar policy masing-masing.
3. Susun daftar ini di laporan sebagai tabel: Connector | Path Secret Dibutuhkan | AppRole Baru (nama) | Policy Baru (nama).

## Tugas 3 — Implementasi AppRole + Policy Per Connector

Untuk **setiap** connector di Tugas 2:

1. Buat policy scoped (contoh pola penamaan: `policy-<connector>-readonly` atau sesuai konvensi lain kalau ditemukan di wiki), isi HCL policy yang hanya mengizinkan path yang relevan (`read`, dan `list` kalau perlu — hindari `write`/`delete` kecuali memang dibutuhkan connector itu).
2. Buat AppRole baru per connector (contoh: `approle-virtualization-collector`, `approle-itsm-connector`, `approle-telegraf-es`), attach ke policy yang sesuai, dengan:
   - `token_ttl` dan `token_max_ttl` yang wajar (ikuti pola 3600/86400 dari fix `dcim-role` sebelumnya, kecuali ada kebutuhan khusus per connector — jelaskan kalau beda).
   - `secret_id_ttl` yang wajar juga (secret_id juga sebaiknya tidak permanen).
3. Generate `role_id` dan `secret_id` untuk tiap AppRole baru, simpan di lokasi yang sudah masuk `.gitignore` (tambahkan pattern baru ke `.gitignore` kalau nama filenya berbeda dari yang sudah ada).
4. **Uji tiap AppRole** dengan login nyata (`vault write auth/approle/login role_id=... secret_id=...`) dan gunakan token hasilnya untuk benar-benar mengakses path secret yang relevan — konfirmasi berhasil untuk path yang diizinkan, dan **gagal (403)** untuk path di luar scope-nya (uji negatifnya juga, jangan cuma uji positif).

## Tugas 4 — Migrasi Referensi Config (Kalau Applicable)

1. Untuk connector yang saat ini masih pakai `dcim-role` generik atau credential hardcoded, update referensinya untuk pakai AppRole baru yang scoped (role_id boleh di config, secret_id tidak).
2. Restart/test ulang service terkait untuk konfirmasi tetap berfungsi dengan AppRole baru.
3. **Jangan hapus/nonaktifkan `dcim-role` lama dulu** di task ini — biarkan tetap ada sebagai fallback sampai migrasi semua connector selesai diverifikasi stabil, baru jadi task terpisah untuk deprecate.

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-approle-per-connector-implementation.md`, TANPA mencantumkan nilai role_id/secret_id/token apapun:

1. **Status Akses Vault (Tugas 0)** — apa yang ditemukan (Vault UI ada/tidak, credential admin tersedia dari mana), dan apakah sempat STOP di tengah jalan karena akses tidak memadai.
2. **Konfirmasi Konvensi Wiki (Tugas 1)** — ringkas ulang, tandai kalau ada temuan baru sejak terakhir dibaca.
3. **Tabel Inventarisasi Connector → AppRole** (dari Tugas 2).
4. **Bukti Implementasi & Uji per AppRole** (Tugas 3) — hasil uji positif (akses berhasil ke path yang diizinkan) dan uji negatif (403 untuk path di luar scope), untuk **setiap** AppRole yang dibuat.
5. **Status Migrasi Config Connector** (Tugas 4) — mana yang sudah pindah ke AppRole baru, mana yang masih pending.
6. **Rekomendasi Next Step** — termasuk kapan `dcim-role` lama sebaiknya di-deprecate, dan konfirmasi apakah root token sekarang sudah siap untuk di-revoke di task berikutnya (ya/tidak, dengan alasan).
