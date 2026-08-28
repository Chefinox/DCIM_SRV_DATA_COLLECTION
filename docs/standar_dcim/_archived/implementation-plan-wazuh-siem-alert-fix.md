# Implementation Plan: Perbaikan Alert Wazuh SIEM — ECONNREFUSED 127.0.0.1:55000

> **Versi**: v1.0
> **Tanggal**: 5 Agustus 2026
> **Status**: DRAFT — MENUNGGU EKSEKUSI (sesi chat baru)
> **Penulis**: Imam Syauqi Achmad
> **Target Host**: Wazuh Manager — `192.168.100.151`
> **Terkait**: Ditemukan saat investigasi indexing `dcim-siem-alerts-*` (implementation plan v4.6.2, Fase Elasticsearch). Bug consumer (`_NO_OFFSET`/crash-loop) sudah diperbaiki terpisah — dokumen ini murni menangani root cause **isi alert itu sendiri**, bukan pipeline pengirimannya.

---

## Latar Belakang

Selama investigasi crash-loop `dcim-siem-es-consumer`, ditemukan bahwa alert yang mengalir ke index `dcim-siem-alerts-*` didominasi oleh pesan berulang dari Wazuh:

```json
{
  "metrics": {
    "type": "log",
    "tags": ["error", "plugins", "wazuh", "cron-scheduler"],
    "pid": 689,
    "message": "Error: connect ECONNREFUSED 127.0.0.1:55000"
  },
  "event_type": "security_alert"
}
```

Pesan ini muncul berulang dengan interval teratur (~15 menit sekali, PID `689` konsisten), sejak minimal 4 Agustus 2026. Ini **bukan** masalah di pipeline DCIM/Kafka/consumer — root cause ada di sisi **Wazuh Manager itu sendiri** (`192.168.100.151`).

**Dugaan awal**: plugin `cron-scheduler` Wazuh (kemungkinan Wazuh Dashboard/Kibana plugin, bukan Wazuh core) mencoba terhubung ke **`127.0.0.1:55000`** (localhost) — port standar Wazuh API (RESTful API `wazuh-apid`, biasanya jalan di `55000`). Karena manager sebenarnya beralamat `192.168.100.151` (bukan localhost dari sudut pandang proses yang mencoba connect), ada dua kemungkinan skenario:
1. Proses yang error **memang berjalan di host manager itu sendiri** (jadi `127.0.0.1` seharusnya valid), tapi service `wazuh-apid`/API tidak berjalan atau tidak listen di port itu.
2. Proses yang error berjalan di host **lain** (misal Wazuh Dashboard di container/host terpisah) yang salah konfigurasi — seharusnya menunjuk ke `192.168.100.151:55000`, bukan `127.0.0.1:55000`.

Kedua skenario ini **belum bisa dipastikan tanpa investigasi langsung** ke host Wazuh Manager — itulah tujuan utama plan ini.

---

## FASE 1 — Investigasi Read-Only di Host Wazuh Manager (192.168.100.151)

### 1.1 Identifikasi proses yang menghasilkan error ini
- SSH ke `192.168.100.151`, cari proses dengan PID `689` (kemungkinan besar sudah berganti PID sejak pertama kali error muncul — cari berdasarkan nama proses, bukan PID literal).
- Kandidat proses: `wazuh-apid`, plugin cron scheduler dari Wazuh Dashboard (jika Dashboard co-located di host yang sama), atau komponen custom lain yang terintegrasi dengan pipeline DCIM.

```bash
ps aux | grep -iE "wazuh|cron-scheduler"
systemctl list-units --type=service | grep -i wazuh
systemctl status wazuh-manager wazuh-apid 2>&1
```

### 1.2 Cek status service API Wazuh
```bash
systemctl status wazuh-apid 2>&1 || systemctl status wazuh-manager 2>&1
ss -tulnp | grep 55000
```
Konfirmasi: apakah port `55000` benar-benar listen di host ini, dan di interface mana (`127.0.0.1` saja, atau `0.0.0.0`/`192.168.100.151`)?

### 1.3 Cek log Wazuh API & Manager untuk detail error
```bash
tail -100 /var/ossec/logs/api.log 2>&1
tail -100 /var/ossec/logs/ossec.log 2>&1 | grep -iE "error|fail|55000"
```

### 1.4 Cek dari mana persis error "cron-scheduler" ini berasal
Kalau Wazuh Dashboard (Kibana-based plugin) yang menghasilkan log ini:
```bash
docker ps | grep -i wazuh 2>&1
docker logs <container_wazuh_dashboard> --tail 100 2>&1 | grep -iE "55000|cron-scheduler|ECONNREFUSED"
```
Cek juga konfigurasi endpoint API yang dipakai Dashboard:
```bash
find / -iname "wazuh.yml" 2>/dev/null
cat <path_wazuh.yml_yang_ditemukan> 2>&1 | grep -A 5 "hosts:\|url:\|port:"
```
Ini KUNCI — kalau ditemukan `url: https://127.0.0.1:55000` di config Dashboard padahal API sebenarnya jalan di host/IP lain, itu konfirmasi skenario 2 (salah konfigurasi endpoint).

### 1.5 Cek histori — sejak kapan persis error ini mulai muncul
```bash
grep -c "ECONNREFUSED" /var/log/syslog 2>/dev/null | tail -5
journalctl -u wazuh-apid --since "7 days ago" --no-pager 2>&1 | grep -iE "start|stop|fail" | head -30
```
Tujuan: cari tahu apakah ini muncul BARU (berkorelasi dengan sesuatu yang berubah baru-baru ini — restart, upgrade, perubahan config) atau sudah lama berlangsung tanpa disadari.

---

## FASE 2 — Analisis & Rencana Perbaikan (Tergantung Hasil Fase 1)

Kemungkinan skenario dan penanganannya (dipilih sesuai temuan Fase 1):

**Skenario A — API service mati/crash**: restart `wazuh-apid`, investigasi kenapa mati (cek resource, cek config `api.yaml`), pasang monitoring/alerting supaya ketahuan lebih cepat kalau mati lagi.

**Skenario B — API listen di interface salah** (misal cuma `127.0.0.1` padahal butuh diakses dari luar): ubah `bind_addr` di `/var/ossec/api/configuration/api.yaml` sesuai kebutuhan, **pertimbangkan implikasi keamanan** (jangan expose API ke `0.0.0.0` tanpa firewall yang benar).

**Skenario C — Dashboard/plugin salah konfigurasi endpoint** (harusnya `192.168.100.151`, tertulis `127.0.0.1`): perbaiki `wazuh.yml`/config terkait di Dashboard, restart service Dashboard.

**Skenario D — Proses testing/leftover yang tidak seharusnya jalan**: matikan proses yang salah, tidak perlu perbaikan config lebih lanjut.

*(Detail langkah eksekusi untuk tiap skenario akan disusun setelah Fase 1 memberi kepastian skenario mana yang berlaku — jangan tebak dan eksekusi skenario tanpa bukti dari Fase 1.)*

---

## FASE 3 — Verifikasi & Penutupan

- Pantau log `api.log`/`ossec.log` beberapa saat pasca-perbaikan, pastikan `ECONNREFUSED 127.0.0.1:55000` tidak muncul lagi.
- Verifikasi index `dcim-siem-alerts-*` di Elasticsearch — pastikan alert BARU yang masuk bukan lagi didominasi pesan error ini, melainkan alert keamanan yang genuine.
- Informasikan ke Tim Security bahwa root cause sudah teridentifikasi dan diperbaiki (bukan masalah di pipeline DCIM).
- (Opsional) Dokumentasikan temuan ini secara singkat, terutama kalau ternyata ini sudah berlangsung lama tanpa diketahui — untuk evaluasi kenapa tidak terdeteksi lebih awal.

---

## Catatan untuk Sesi Baru

- Dokumen ini murni untuk masalah **isi/asal alert Wazuh**, terpisah dari perbaikan pipeline consumer (`dcim-siem-es-consumer`) yang sudah selesai di sesi sebelumnya (commit `c87bc74`, implementation plan v4.6.2).
- Host target (`192.168.100.151`) **di luar** `srv-rnd-dcim` (`10.70.0.56`) yang jadi fokus sesi-sesi sebelumnya — pastikan agent yang menjalankan plan ini punya akses SSH/eksekusi ke host Wazuh Manager tersebut.
- Ikuti pola kerja standar: investigasi read-only dulu (Fase 1), baru rencana perbaikan dengan approval eksplisit sebelum eksekusi (Fase 2), verifikasi menyeluruh sebelum ditutup (Fase 3).
