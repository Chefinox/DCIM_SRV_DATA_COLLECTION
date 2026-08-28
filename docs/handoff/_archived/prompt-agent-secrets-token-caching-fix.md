# Prompt untuk Agent: Fix Token Caching di `secrets.py` + Commit Policy HCL sebagai Kode

## Konteks

Implementasi AppRole per-connector (`docs/handoff/2026-08-20-agent-handoff-approle-per-connector-implementation.md`, commit `392c51e`) sudah benar dari sisi desain isolasi (4 AppRole scoped, terbukti lolos test positif+negatif). Tapi ada **bug perilaku yang direplikasi dari masalah lama**: fungsi `get_secret()` di `src/utils/secrets.py` memanggil `client.auth.approle.login(...)` **setiap kali dipanggil**, tanpa caching/reuse token sama sekali.

Ini persis pola yang sebelumnya diidentifikasi sebagai root cause 289K lease menumpuk pada `dcim-role` (laporan 19 Agustus: *"script seharusnya reuse token sampai expired, bukan re-login setiap request"*). `token_ttl=3600` yang sekarang dipasang di 4 AppRole baru membuat lease auto-expire (tidak permanen seperti dulu), tapi **tidak menghilangkan perilaku boros re-login di tiap pemanggilan** — kalau frekuensi panggilan `get_secret()` tinggi (mis. dipanggil tiap siklus `ExecuteProcess` NiFi), lease baru tetap terus-menerus tercipta dan berisiko menumpuk mendekati threshold lagi, hanya lebih lambat dari sebelumnya.

## Batasan Keras (Do Not)

- **JANGAN cuma menaikkan TTL lebih lanjut sebagai "solusi"** — itu memperlambat gejala, bukan memperbaiki perilaku re-login yang salah. Root cause-nya harus diperbaiki di level kode: token di-reuse, bukan di-generate ulang tiap panggilan.
- **JANGAN simpan token yang di-cache dalam bentuk plaintext di file yang ter-commit ke git** — kalau caching disimpan di file lokal (bukan cuma in-memory), pastikan lokasinya sudah masuk `.gitignore` dengan pola yang sama seperti `role_id_*`/`secret_id_*`.
- **JANGAN mengubah struktur AppRole/policy yang sudah ada** (4 AppRole scoped yang sudah diverifikasi) — task ini murni memperbaiki cara `secrets.py` menggunakan AppRole itu, bukan mendesain ulang isolasinya.
- **JANGAN commit nilai secret Vault apapun ke policy HCL** — policy HCL cuma berisi path pattern + capability (`read`, `list`, dsb), tidak pernah mengandung nilai secret sungguhan, jadi aman di-commit — tapi tetap audit sebelum commit untuk pastikan tidak ada yang salah tempel.

## Tugas 1 — Implementasi Token Caching/Reuse di `secrets.py`

1. Tambahkan mekanisme cache token per-connector (bisa in-memory dict kalau proses long-running, atau cache berbasis file dengan expiry timestamp kalau tiap pemanggilan script adalah proses baru/short-lived seperti yang dieksekusi NiFi `ExecuteProcess`):
   - **Kalau proses long-running** (service yang jalan terus, bukan dieksekusi ulang tiap kali): simpan token + waktu expiry di variable module-level, cek dulu sebelum login apakah token yang di-cache masih valid (belum lewat `token_ttl`, beri buffer waktu mis. 60 detik sebelum expiry aktual untuk hindari race condition).
   - **Kalau proses short-lived per-invocation** (skrip yang dipanggil ulang tiap siklus NiFi `ExecuteProcess`, sehingga in-memory cache tidak berguna karena proses selalu baru): simpan token hasil login ke file cache lokal (per-connector, mis. `vault/cache/token_<connector>.json` berisi token + expiry timestamp), baca file itu dulu di awal `get_secret()` — kalau masih valid, pakai langsung tanpa login ulang; kalau sudah/hampir expired, baru login ulang dan update cache file.
   - **Konfirmasi dulu mana pola yang sebenarnya terjadi di project ini** (cek bagaimana `ExecuteProcess` NiFi menjalankan script-script poller — apakah tiap eksekusi adalah proses Python baru atau ada mekanisme daemon/long-running) sebelum memilih pendekatan, supaya fix-nya benar-benar mengatasi pola pemanggilan yang sesungguhnya terjadi, bukan asumsi.
2. Tambahkan pola cache file (kalau dipakai) ke `.gitignore`.
3. Pastikan ada fallback aman: kalau file cache corrupt/tidak terbaca, kode tetap fallback ke login normal (jangan sampai malah crash karena cache rusak).
4. Tambahkan sedikit logging/print (level debug) untuk membedakan "menggunakan token dari cache" vs "login baru ke Vault" — ini akan memudahkan verifikasi Tugas 3 di bawah.

## Tugas 2 — Uji Bahwa Reuse Benar-Benar Terjadi

1. Panggil `get_secret()` untuk secret yang sama beberapa kali berturut-turut dalam window singkat (simulasikan pola pemanggilan nyata dari poller/consumer) — konfirmasi lewat log yang ditambahkan di Tugas 1.4 bahwa **hanya panggilan pertama** yang benar-benar login ke Vault, panggilan berikutnya pakai token dari cache.
2. Cek jumlah lease baru yang tercipta di Vault selama uji ini (`vault list sys/leases/lookup/auth/approle/login/<connector>` atau metode setara) — bandingkan sebelum dan sesudah fix, buktikan jumlah lease baru **jauh lebih sedikit** dibanding jumlah pemanggilan `get_secret()`.
3. Uji juga skenario token expired (mis. paksa expiry cache lebih cepat untuk testing) — konfirmasi kode benar login ulang saat memang diperlukan, bukan pakai token basi.

## Tugas 3 — Commit Policy HCL sebagai Infrastructure-as-Code

1. Export definisi 4 policy yang sudah dibuat di Vault (`policy-elasticsearch-readonly`, `policy-postgres-readonly`, `policy-redfish-readonly`, `policy-ralph-readonly`) ke file HCL lokal, mis. di `vault/policies/<nama-policy>.hcl`.
2. Audit tiap file HCL sebelum commit — pastikan isinya cuma path pattern + capability, tidak ada nilai secret/token apapun yang ikut ke-embed.
3. Commit file-file ini ke repo sebagai source of truth infrastructure-as-code, supaya kalau Vault perlu di-rebuild, definisi policy tidak hilang.
4. Tambahkan catatan singkat di README/dokumentasi terkait (kalau ada tempat yang sesuai) bahwa policy HCL di `vault/policies/` adalah source of truth — perubahan policy sebaiknya diedit di file ini dulu lalu di-apply ke Vault (`vault policy write`), bukan diubah langsung di Vault lalu lupa disinkronkan balik ke repo.

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-secrets-token-caching-fix.md`:

1. **Analisis Pola Pemanggilan** — hasil konfirmasi Tugas 1.3 (short-lived vs long-running), dan pendekatan caching yang dipilih berdasarkan itu.
2. **Bukti Reuse Token Bekerja** — hasil Tugas 2, termasuk perbandingan jumlah lease baru sebelum/sesudah fix untuk jumlah pemanggilan yang sama.
3. **Bukti Fallback Aman** — konfirmasi cache corrupt tidak menyebabkan crash.
4. **Status Policy HCL** — konfirmasi 4 file HCL sudah di-commit dan diaudit bersih dari secret.
5. **Kesimpulan** — apakah root cause re-login berlebihan ini sekarang benar-benar teratasi (bukan cuma tertunda oleh TTL), dengan bukti konkret.
