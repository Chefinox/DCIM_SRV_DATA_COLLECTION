# Prompt untuk Agent: Remediasi Penuh Vault — Git History Cleanup, Generate Root Token, Cleanup Lease, dan .gitignore

## Konteks

Owner (Imam Syauqi Achmad) **mengizinkan agent mengeksekusi langsung** empat aksi yang sebelumnya diserahkan ke owner secara manual:
1. `git filter-repo` untuk membersihkan token Vault lama dari seluruh riwayat git + force-push.
2. Generate root token Vault baru (token lama di `init.txt` sudah invalid sejak 30 Juli 2026).
3. Cleanup Vault lease yang melebihi threshold (289,390 lease aktif vs threshold 256,000).
4. Menambahkan `vault/config/init.txt` ke `.gitignore`.

Ini pengecualian eksplisit dari batasan "jangan eksekusi aksi destruktif sendiri" pada prompt-prompt sebelumnya — **hanya untuk empat aksi ini**, bukan izin umum untuk aksi destruktif lain di luar scope task ini (migrasi ES ke Vault dan fix DLQ isolation TETAP di luar izin, lihat Batasan Keras).

## Batasan Keras (Do Not)

- **JANGAN tulis nilai token baru (root token hasil generate, maupun token lama yang sedang dibersihkan) di file manapun yang ter-commit ke git** — ini sudah terjadi berulang kali. Root token baru harus disimpan di tempat yang **tidak** ter-track git (lihat Tugas 2.4).
- **JANGAN lanjutkan ke Tugas 2 (generate token baru) sebelum Tugas 1 (git history cleanup) selesai dan terverifikasi** — supaya kalau nanti perlu tulis token baru sementara ke `init.txt` lokal, file itu sudah pasti masuk `.gitignore` dan tidak akan ter-commit lagi.
- **JANGAN scope creep** ke aksi lain yang belum diizinkan eksplisit (migrasi credential ES ke Vault, fix DLQ error isolation di `mikrotik_poller.py`/`cctv_poller.py`) — itu di luar izin task ini, cukup dicatat sebagai next step di laporan.
- **JANGAN eksekusi `git push --force` tanpa langkah verifikasi & backup di bawah** — ini operasi ireversibel terhadap remote history.

## Tugas 1 — Eksekusi Git History Cleanup (Aksi #1)

1. **Backup dulu sebelum rewrite apapun**: buat clone penuh repo saat ini ke lokasi terpisah (mis. `/tmp/dcim-repo-backup-pre-filter-repo`) sebagai safety net kalau filter-repo menghasilkan hal tak terduga.
2. Konfirmasi tidak ada perubahan lokal yang belum di-commit (`git status` bersih) sebelum mulai.
3. Jalankan instruksi yang sudah disiapkan di laporan sebelumnya (Section 1.2) — baca token dari `init.txt` secara dinamis ke file pola sementara, jangan hardcode nilainya di command manapun yang tercatat di log/laporan:
   ```bash
   sudo apt install git-filter-repo
   TOKEN=$(grep "Initial Root Token:" vault/config/init.txt | awk '{print $NF}')
   echo "${TOKEN}==>VAULT_ROOT_TOKEN_REDACTED" > /tmp/vault-token-replace.txt
   git filter-repo --replace-text /tmp/vault-token-replace.txt --force
   rm -f /tmp/vault-token-replace.txt
   ```
4. **Cek juga apakah ada nilai credential lain yang perlu ikut dibersihkan** dari history (mis. password Elasticsearch dari laporan sebelumnya, kalau belum pernah di-filter) — kalau ada, tambahkan ke file pola yang sama sebelum run `filter-repo` supaya cukup sekali rewrite history, bukan berkali-kali.
5. Sebelum force-push, **verifikasi lokal**: `git log -p | grep` untuk nilai token lama dan password ES lama — pastikan hasilnya kosong.
6. Tambahkan `vault/config/init.txt` ke `.gitignore` sebelum push (supaya file ini tidak ter-track lagi setelahnya).
7. Push dengan `--force-with-lease` (bukan `--force` polos, untuk menghindari overwrite perubahan orang lain yang mungkin masuk di antara waktu ini):
   ```bash
   git push origin main --force-with-lease
   ```
8. **Verifikasi dari sisi remote**: lakukan fresh clone repo ke direktori baru, jalankan `git log -p | grep` lagi untuk nilai token/password lama — konfirmasi benar-benar hilang dari remote, bukan cuma lokal.
9. Catat di laporan: **peringatan eksplisit bahwa semua collaborator lain wajib re-clone repo** (bukan `git pull`) karena history sudah di-rewrite — sertakan kalimat ini jelas di laporan supaya owner bisa broadcast ke tim.

## Tugas 2 — Generate Root Token Vault Baru (Aksi #2)

1. Konfirmasi ketersediaan **unseal keys** (biasanya tercatat bersama root token lama di `init.txt` atau tempat terpisah) — proses generate root token baru butuh quorum unseal key (`vault operator generate-root`).
2. Jalankan proses generate root token sesuai prosedur resmi Vault:
   ```bash
   vault operator generate-root -init
   # ikuti proses OTP/nonce, submit unseal key sesuai threshold
   vault operator generate-root -decode=<encoded_token> -otp=<otp>
   ```
3. **JANGAN simpan token baru ke `init.txt` yang lama** (pola ini yang menyebabkan kebocoran berulang). Simpan di lokasi yang eksplisit **tidak** ter-track git — kalau perlu di file lokal, pastikan pathnya sudah masuk `.gitignore` sebelum file itu dibuat (bukan sesudah).
4. **Rekomendasi struktural** (lakukan kalau memungkinkan dalam scope ini, tanpa root token permanen jadi kebiasaan): setelah root token baru berhasil dipakai untuk keperluan admin mendesak, buat **AppRole/policy scoped** untuk kebutuhan automation rutin (migrasi credential, dsb — untuk task selanjutnya), lalu **revoke root token baru ini segera setelah tidak dibutuhkan** supaya tidak ada root token hidup lama-lama yang berisiko bocor lagi seperti pola sebelumnya. Root token sebaiknya hanya dipakai sesaat untuk provisioning awal, bukan disimpan permanen untuk dipakai berulang oleh agent.
5. Uji token baru: `vault token lookup` untuk konfirmasi valid dan punya privilege yang cukup.
6. Laporkan ke owner **cara mengakses token baru ini secara aman** (lokasi file lokal, atau — lebih baik — serahkan langsung nilainya ke owner via saluran privat, bukan dicatat di file/laporan apapun).

## Tugas 3 — Cleanup Vault Lease yang Melebihi Threshold (Aksi #3)

1. Dengan token admin (root token baru dari Tugas 2, atau token dengan privilege cukup), cek breakdown lease aktif per auth method/path terlebih dahulu sebelum revoke massal — jangan asal `revoke -prefix` tanpa tahu apa yang akan kena dampak:
   ```bash
   vault list sys/leases/lookup/auth/approle/login/
   ```
2. Identifikasi apakah 289,390 lease ini wajar (mis. AppRole login yang sangat sering terjadi dari banyak service) atau indikasi ada proses yang leak/tidak pernah revoke lease dengan benar (mis. loop retry yang re-login tanpa reuse token). **Laporkan root cause ini**, jangan cuma revoke tanpa tahu penyebabnya — kalau memang ada proses yang salah pola (re-login setiap request alih-alih reuse token sampai expired), itu perlu diperbaiki juga supaya lease tidak menumpuk lagi di masa depan.
3. Revoke lease yang memang sudah tidak relevan/expired secara bertahap (bukan sekaligus prefix luas yang bisa mematikan sesi service yang masih aktif dipakai):
   ```bash
   vault lease revoke -prefix auth/approle/login/
   ```
   Pertimbangkan revoke bertahap per sub-path kalau volumenya besar, dan pantau apakah ada service yang tiba-tiba gagal auth setelah revoke (indikasi lease itu ternyata masih dipakai aktif).
4. Setelah cleanup, cek ulang lease count (`vault read sys/internal/counters/tokens` atau metric relevan) — konfirmasi sudah di bawah threshold 256,000.
5. Kalau root cause-nya adalah pola re-login yang salah di salah satu service/script project ini, catat sebagai temuan terpisah untuk task perbaikan lanjutan (di luar scope eksekusi task ini, cukup dilaporkan).

## Tugas 4 — Tambahkan `init.txt` ke `.gitignore` (Aksi #4)

Langkah ini sudah termasuk di Tugas 1 langkah 6 (harus dilakukan sebelum push, supaya file tidak ter-track lagi setelah history dibersihkan). Konfirmasi ulang di laporan bahwa:
1. `vault/config/init.txt` sudah tercantum di `.gitignore`.
2. File `init.txt` versi saat ini (kalau masih ada secret lama di dalamnya) sudah tidak lagi muncul di `git status` sebagai tracked file.
3. Commit terpisah untuk perubahan `.gitignore` ini dibuat dengan pesan yang jelas (mis. `security: add vault/config/init.txt to .gitignore`).



Buat `docs/handoff/YYYY-MM-DD-agent-handoff-vault-full-remediation.md`, TANPA mencantumkan nilai token/password apapun di dalamnya:

1. **Status Git History Cleanup** — bukti verifikasi lokal & remote (hasil grep kosong), konfirmasi `.gitignore` sudah update, dan **peringatan re-clone untuk tim** ditulis jelas.
2. **Status Root Token Baru** — konfirmasi token berhasil digenerate dan valid (tanpa menuliskan nilainya), lokasi penyimpanan aman yang dipakai, dan status apakah token ini sudah direvoke kembali setelah dipakai atau masih aktif (dan kenapa).
3. **Status Cleanup Lease** — angka lease sebelum/sesudah, root cause temuan (kalau ada pola re-login yang salah), dan konfirmasi tidak ada service yang tiba-tiba gagal auth akibat revoke.
4. **Status `.gitignore` init.txt** — konfirmasi sesuai Tugas 4.
5. **Rekomendasi Struktural** — apakah AppRole/policy scoped sudah dibuat sebagai pengganti ketergantungan root token, atau masih jadi next step terpisah.
6. **Scope yang Sengaja Tidak Dikerjakan** — tegaskan migrasi ES ke Vault dan fix DLQ isolation TIDAK termasuk task ini, masih menunggu izin/task terpisah.
