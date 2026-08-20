# Handoff Report: Vault Token Cleanup & Kafka KRaft Quorum Recovery

**Date:** 2026-08-19
**Author:** GitHub Copilot

---

## 1. Status Cleanup Token Vault

### 1.1 Redaksi File yang Terpengaruh

Nilai Vault root token yang tertulis plaintext telah dihapus dari **4 file** berikut:

| File | Status |
|------|--------|
| `docs/handoff/2026-08-19-agent-handoff-credential-remediation-and-kafka-recovery.md` | ✅ Redacted |
| `docs/handoff/2026-08-18-agent-handoff-gui-dependent-tasks.md` | ✅ Redacted |
| `docs/handoff/2026-08-18-agent-handoff-nifi-access-recovery-and-fix.md` | ✅ Redacted |
| `docs/handoff/prompt-agent-vault-cleanup-kafka-quorum-recovery.md` | ✅ Redacted |

Semua referensi diganti dengan deskripsi netral: *"token root yang tercatat di `vault/config/init.txt`"*.

**Commit:** `f61ec3b` — `security: redact Vault root token from all handoff reports`

### 1.2 Instruksi Git History Cleanup (Owner Harus Eksekusi Manual)

Karena token sudah pernah ter-commit ke git history, Owner **harus** menjalankan perintah berikut di lokal untuk membersihkan riwayat:

```bash
# 1. Install git-filter-repo (jika belum ada)
sudo apt install git-filter-repo

# 2. Buat file pola pengganti (JANGAN isi nilai token asli di sini — ambil dari init.txt)
#    Baca token dari init.txt, lalu masukkan ke file pola:
TOKEN=$(grep "Initial Root Token:" vault/config/init.txt | awk '{print $NF}')
echo "${TOKEN}==>VAULT_ROOT_TOKEN_REDACTED" > /tmp/vault-token-replace.txt

# 3. Jalankan filter-repo
cd /home/infra/dcim_metrics_project
git filter-repo --replace-text /tmp/vault-token-replace.txt --force

# 4. Bersihkan file pola
rm -f /tmp/vault-token-replace.txt

# 5. Force push ke remote (PERINGATAN: ini mengubah seluruh commit history)
git push origin main --force-with-lease

# 6. Beritahu semua collaborator untuk re-clone repo
```

### 1.3 Catatan: init.txt Juga Sebaiknya Tidak Di-commit

File `vault/config/init.txt` yang berisi unseal key dan root token **sebaiknya ditambahkan ke `.gitignore`** agar tidak ter-commit di masa depan:

```bash
echo "vault/config/init.txt" >> .gitignore
git add .gitignore && git commit -m "security: add vault/config/init.txt to .gitignore"
```

---

## 2. Klarifikasi Status Token Vault

### Temuan Faktual

| Aspek | Hasil |
|-------|-------|
| **Vault Server** | Running, unsealed, healthy (`hashicorp/vault:1.15`, container `vault`, uptime 8 hari) |
| **Token Lookup** | `403 Permission Denied` — token di `init.txt` **tidak valid lagi** |
| **Root Cause** | Log Vault menunjukkan **4 kali "root generation"** pada tanggal **2026-07-30**. Artinya root token telah di-regenerate (kemungkinan oleh administrator), sehingga token asli di `init.txt` otomatis invalid. |
| **Vault Health** | `Initialized: true, Sealed: false, HA: false` |
| **Lease Warning** | ⚠️ Vault terus mengeluarkan warning: `lease count exceeds warning lease threshold: have=289390 threshold=256000` — ada **289,390 lease aktif** yang melebihi threshold 256,000. Perlu cleanup lease oleh admin. |

**Kesimpulan:** Token di `init.txt` sudah **tidak valid** karena root token di-regenerate pada 30 Juli 2026. Untuk mendapatkan akses admin Vault, Owner perlu menggunakan root token baru yang dihasilkan saat regeneration tersebut, atau generate root token baru menggunakan unseal key.

**Rekomendasi tambahan:** Lease count yang sangat tinggi (289K+) bisa menyebabkan degradasi performa Vault. Owner sebaiknya menjalankan cleanup:
```bash
# Masuk ke container vault dengan token admin yang valid
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=<NEW_ROOT_TOKEN> vault vault lease revoke -prefix auth/approle/login/
```

---

## 3. Bukti DLQ Writer Fix — Audit Threading

### Hasil Audit

Keempat poller script telah diaudit untuk arsitektur threading dan cakupan `sys.excepthook`:

| Script | Concurrency Model | `sys.excepthook` | Threading? | Per-device try-except |
|--------|-------------------|-------------------|------------|----------------------|
| `mikrotik_poller.py` | Sequential + subprocess | ✅ Line 24 | ❌ Tidak ada | ⚠️ Tidak ada except clause di loop utama |
| `redfish_poller.py` | Sequential + requests | ✅ Line 22 | ❌ Tidak ada | ✅ Line 289 |
| `nas_poller.py` | Sequential + subprocess | ✅ Line 25 | ❌ Tidak ada | ✅ Line 140 |
| `cctv_poller.py` | Sequential + requests | ✅ Line 24 | ❌ Tidak ada | ⚠️ Tidak ada di main() |

### Kesimpulan Threading

- **Tidak ada threading/asyncio/multiprocessing** di keempat poller — semuanya sequential.
- `threading.excepthook` **tidak diperlukan** karena tidak ada thread worker.
- `sys.excepthook` sudah terpasang di semua poller dengan `global_exception_handler` yang menghasilkan JSON error event.

### Risiko Tersisa (Non-threading)

1. **`mikrotik_poller.py`**: Loop utama tidak punya `except` clause — exception di satu device akan abort semua device berikutnya (akan ditangkap `sys.excepthook` tapi semua IP selanjutnya terlewat).
2. **`cctv_poller.py`**: `main()` tidak punya `try-except` per-kamera — satu kamera gagal = semua gagal.
3. **`nas_poller.py`**: `limiter.acquire()` dipanggil tanpa `finally: limiter.release()` — rate limiter slot bisa bocor.

### Status DLQ Writer Fix

**Verdict: Partially Fixed** — `sys.excepthook` berhasil mencegah plaintext traceback ke NiFi. Namun error isolation per-device masih lemah di 2 dari 4 poller (`mikrotik` dan `cctv`). Tidak ada dedicated DLQ writer module — logika DLQ routing tertanam inline di `src/skills/telemetry/normalizer/executor.py`.

---

## 4. Bukti Mock API Health (ST-391/392)

### Proxmox Fixture Adapter (port 8081)

| Metric | Value |
|--------|-------|
| PID | 3717754 |
| Uptime | 6 hari 1 jam (sejak 13 Aug 16:52) |
| Memory (RSS) | 18,996 KB |
| CPU | 1.2% |
| Test Response | ✅ Valid JSON dengan 3 VM entries (PROD-SRV-WEB, DEV-DB-01, TEST-APP-01) |

### ITSM Fixture API (port 8083)

| Metric | Value |
|--------|-------|
| PID | 3870968 |
| Uptime | 6 hari 0 jam (sejak 13 Aug 17:42) |
| Memory (RSS) | 19,092 KB |
| CPU | 0.0% |
| Test Response | ✅ POST `/api/now/table/incident` berhasil — returns `sys_id`, `number`, `short_description`, `state` |

**Verdict: Healthy** ✅ — Kedua mock adapter merespons sesuai skema, uptime stabil, resource usage normal.

---

## 5. Status Pemulihan Kafka KRaft Quorum

### Root Cause

`kafka3` ter-kill oleh SIGKILL (exit code 137) pada **2026-08-19 03:41:22 UTC** — kemungkinan OOM killer atau manual stop. Dengan `kafka3` down, quorum 3-node KRaft kehilangan satu voter. `kafka1` dan `kafka2` terus mencoba connect ke `kafka3:9093` tapi gagal (`UnknownHostException` karena container mati dan DNS Docker tidak resolve).

### Investigasi meta.properties

| Node | cluster.id | node.id | directory.id | Status |
|------|-----------|---------|--------------|--------|
| kafka1 | `5L6g3nShT-eMCtK--X86sw` | 1 | `nAqE4janB9YEUTjHzkENjg` | ✅ Konsisten |
| kafka2 | `5L6g3nShT-eMCtK--X86sw` | 2 | `noMC1VVBWdIUYAcZqFLpRw` | ✅ Konsisten |
| kafka3 | `5L6g3nShT-eMCtK--X86sw` | 3 | `CQHn8Sq20tefYWdLzHFwbw` | ✅ Konsisten |

**Tidak ada split-brain atau metadata mismatch** — semua node memiliki `cluster.id` yang sama.

### Tindakan Pemulihan

Karena metadata sehat dan hanya perlu restart, tindakan ini aman (non-destruktif):

```bash
docker compose -f docker-compose-cluster.yml start kafka3
```

Kafka3 berhasil start, recovery snapshot metadata (`__cluster_metadata-0`), dan join kembali ke quorum.

### Bukti Quorum Sehat

```
ClusterId:              5L6g3nShT-eMCtK--X86sw
LeaderId:               1
LeaderEpoch:            31195
HighWatermark:          2228788
MaxFollowerLag:         0
MaxFollowerLagTimeMs:   0
CurrentVoters:          [node 1 (kafka1:9093), node 2 (kafka2:9093), node 3 (kafka3:9093)]
CurrentObservers:       []
```

### Bukti Replikasi Sehat

```
NodeId  LogEndOffset    Lag     Status
1       2228847         0       Leader
2       2228847         0       Follower
3       2228847         0       Follower
```

### Consumer Groups — Semua Sehat, Lag 0

```
nifi-enrichment-group
dcim-es-consumer
dcim-analytics-bridge
dcim_dlq_persistence_group
dcim-siem-es-consumer-2
analytics-stream-processor
dcim_python_normalizer_group
dcim-postgres-consumer-v2
dcim_itop_group_v8
```

Semua consumer group merespons tanpa timeout, consumer lag = 0 di semua partition.

---

## 6. Hasil Load Test ST-394

Kafka sudah sehat, load test dilakukan 2 kali menggunakan `tests/load_testing/kafka_locustfile.py` (5 users, 30s, via Python 3.12 venv):

### Run 1

| Metric | Produce Valid Event | Produce Invalid Event | Aggregated |
|--------|--------------------|-----------------------|------------|
| Request Count | 3,169 | 1,061 | **4,230** |
| Failure Count | **0** | **0** | **0** |
| Avg Response Time (ms) | 1.87 | 1.94 | **1.88** |
| Min Response Time (ms) | 1.02 | 0.98 | 0.98 |
| Max Response Time (ms) | 71.34 | 104.20 | 104.20 |
| Median (ms) | 2 | 2 | 2 |
| P95 (ms) | 3 | 3 | 3 |
| P99 (ms) | 3 | 3 | 3 |
| Requests/s | 113.04 | 37.85 | **150.89** |

### Run 2

| Metric | Produce Valid Event | Produce Invalid Event | Aggregated |
|--------|--------------------|-----------------------|------------|
| Request Count | 3,486 | 1,102 | **4,588** |
| Failure Count | **0** | **0** | **0** |
| Avg Response Time (ms) | 1.87 | 1.77 | **1.84** |
| Min Response Time (ms) | 0.98 | 1.04 | 0.98 |
| Max Response Time (ms) | 107.78 | 14.82 | 107.78 |
| Median (ms) | 2 | 2 | 2 |
| P95 (ms) | 2 | 2 | 2 |
| P99 (ms) | 3 | 3 | 3 |
| Requests/s | 117.24 | 36.85 | **153.93** |

**ST-394 Verdict: PASS** ✅ — 0 failures di kedua run, konsistensi throughput ~150 req/s, latency sub-2ms.

---

## 7. Kesimpulan Kesehatan Pipeline

| Komponen | Status | Catatan |
|----------|--------|---------|
| **Kafka KRaft Quorum** | ✅ **Healthy** | 3/3 voter aktif, lag 0, quorum terbentuk |
| **Kafka Load Test (ST-394)** | ✅ **Pass** | 0 failures, ~150 req/s, <2ms latency |
| **Consumer Groups** | ✅ **Healthy** | 9 groups aktif, lag 0 |
| **Mock API (ST-391/392)** | ✅ **Healthy** | Kedua adapter responsif, uptime 6 hari |
| **DLQ Writer sys.excepthook** | ⚠️ **Partially Fixed** | Terpasang di 4 poller tapi error isolation per-device lemah di mikrotik & cctv |
| **Vault Token** | 🔴 **Blocked** | Token di init.txt invalid (sudah di-regenerate). Owner perlu generate/gunakan token baru |
| **Vault Lease Count** | ⚠️ **Warning** | 289,390 lease aktif melebihi threshold 256,000 |
| **Git History Cleanup** | 🟡 **Menunggu Owner** | Instruksi `filter-repo` sudah disiapkan, harus dieksekusi manual |
| **NiFi RouteOnContent** | 🔴 **Menunggu Owner** | Modifikasi kanvas NiFi harus via GUI oleh admin |

### Status Keseluruhan: **PARTIALLY RECOVERED**

- ✅ Kafka quorum **berhasil dipulihkan** — pipeline data streaming sudah aktif kembali.
- ✅ Token Vault **berhasil di-redact** dari semua file, menunggu git history cleanup oleh Owner.
- ⚠️ Vault access **masih blocked** — Owner perlu generate root token baru atau gunakan token hasil regeneration 30 Juli.
- ⚠️ DLQ error isolation perlu perbaikan lanjutan di `mikrotik_poller.py` dan `cctv_poller.py`.

### Aksi yang Masih Dibutuhkan dari Owner

1. **[URGENT]** Eksekusi `git filter-repo` untuk bersihkan token dari git history (lihat instruksi di Section 1.2).
2. **[HIGH]** Provide root token Vault yang baru, atau generate ulang via `vault operator generate-root`.
3. **[HIGH]** Cleanup Vault lease (`289,390` aktif, melebihi threshold).
4. **[MEDIUM]** Tambahkan `vault/config/init.txt` ke `.gitignore`.
5. **[LOW]** Perbaiki error isolation di `mikrotik_poller.py` dan `cctv_poller.py`.
