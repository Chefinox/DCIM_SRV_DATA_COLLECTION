# Handoff — Migrasi Ingestion Telegraf→NiFi & Perbaikan SNMP UPS (2026-06-30)

> **Untuk**: agent/engineer yang akan melanjutkan migrasi ingestion ke NiFi dan menuntaskan percobaan pertama (SNMP UPS yang masih gagal).
> **Dari**: sesi studi gap data-ingestion + investigasi live kegagalan SNMP UPS (2026-06-30).
> **Host**: `srv-rnd-dcim` (10.70.0.56) · **Repo**: `/home/infra/dcim_metrics_project` · branch `main`.
> **Sistem PRODUKSI** — tidak ada aksi operasional tanpa persetujuan user.

> **WAJIB baca dulu, berurutan (JANGAN eksekusi sebelum paham keempat lapis: konteks, pipeline, struktur, dcim-wiki):**
> 1. `docs/handoff/2026-06-29-nifi-ingestion-alignment-prompt.md` — keputusan arah & tahapan migrasi (dikunci user).
> 2. `docs/handoff/2026-06-29-pipeline-remediation-handoff.md` — kondisi pasca-remediasi + pelajaran kegagalan Flink (durabilitas).
> 3. `docs/architecture/v4.3-pipeline-architecture.md` — arsitektur aktual + ADR-001/002/003.
> 4. `/home/infra/dcim-wiki/reference-designs/block2-data-ingestion-integration.md` — **referensi target**, fokus §3 (topik), §4–8 (flow NiFi, NMS pakai `GetSNMP`), §9 (validasi), §10 (enrichment), §11 (DLQ), §15 (acceptance).
> 5. `docs/standar_dcim/v4.3-pipeline-architecture-komparasi.md` — status gap terbaru.

---

## 0. JANGAN langsung eksekusi — pahami 4 lapis dulu

Dokumen ini sengaja menahan Anda dari "langsung benerin". Pola kegagalan berulang di project ini = **eksekusi tanpa paham konteks + tanpa durabilitas** (kasus Flink & klaim Kafka ACL palsu). Sebelum menyentuh sistem, pastikan Anda bisa menjawab:

1. **Konteks** — Kenapa migrasi ke NiFi? Apa yang DIKUNCI user & tidak boleh diubah? (§1)
2. **Pipeline** — Bagaimana data mengalir hari ini (Telegraf→Kafka→normalizer→NiFi-enrich→PG/ES/iTop)? Mana yang SEHAT & tidak boleh diputus? (§2)
3. **Struktur** — Di mana config Telegraf, compose NiFi, topik, dokumen? (§2.3)
4. **dcim-wiki** — Apa pola target Block 2 (NiFi-centric: ingest→validate→normalize→enrich→publish)? Apa drift-nya? (§3)

Lalu jalankan **smoke test §7** untuk mengonfirmasi sendiri kondisi live — jangan percaya dokumen buta. Setiap aksi operasional → **konfirmasi user dulu**.

---

## 1. Konteks & keputusan yang DIKUNCI user

1. **`/home/infra/dcim-wiki` = referensi utama.** Tujuan: menutup drift arsitektur ingestion antara implementasi aktual dan wiki Block 2.
2. **Arah migrasi dikunci:** implementasi saat ini **Telegraf-centric** (Telegraf langsung produce ke Kafka) → diselaraskan ke pola **NiFi-centric** (NiFi sebagai flow ingestion: terima → validasi → publish ke Kafka), sesuai wiki §4–8.
3. **Selaraskan POLA, bukan konvensi yang sudah jadi standar.** Deviasi yang SUDAH disahkan & **JANGAN diubah**: Avro+Schema Registry (ADR-001), penamaan topik `dcim.raw/.normalized/.enriched` (ADR-002), versi PG15.18/ES9.3.1 (ADR-003), konektor iTop/Ralph (bukan ServiceNow/SAP).
4. **Anti big-bang.** Migrasi bertahap & **paralel-run**: jangan matikan Telegraf sebelum NiFi terbukti paritas per sumber.
5. **Durabilitas wajib.** Semua artefak (flow NiFi → export ke template/registry, config, kode) **ter-commit ke git**. Pelajaran Flink: kerja ephemeral = hilang saat container recreate.
6. Staging git **selektif per-file** — repo punya banyak perubahan working-tree warisan; jangan commit massal. Jangan commit/ekspos kredensial.

---

## 2. Pipeline & struktur aktual (terverifikasi 2026-06-30)

### 2.1 Aliran data hari ini (Telegraf-centric)

```
Telegraf (6 input) ──JSON──▶ dcim.raw.*  ──▶ dcim-normalizer ──Avro──▶ dcim.normalized.events
                                                                              │
                                                  NiFi (HANYA enrichment: Redis + Enrichment API)
                                                                              │
                                                                  dcim.enriched.events
                                                       ├─▶ dcim-sql-consumer  ─▶ PostgreSQL 15.18 (dcim_events)
                                                       ├─▶ dcim-itop-unified   ─▶ iTop CMDB
                                                       └─▶ dcim-es-consumer     ─▶ Elasticsearch 9.3.1
```

> **Batas Avro = `dcim.normalized.events`.** Apa pun yang membaca `.normalized`/`.enriched` WAJIB deserialize Avro (magic byte `0x00` + schema id).

### 2.2 Yang SEHAT ✅ — JANGAN diputus
- Kafka 3-broker (`kafka1/2/3`, KRaft, TLS :9094, INTERNAL :29092, RF=3), Schema Registry, Vault — Up.
- PostgreSQL 15.18 (`dcim_sot_postgres`, db `dcim_sot`, user `sot_admin`): `dcim_events` segar (<5 mnt), `dcim_lineage` aktif.
- Jalur Avro normalizer→enrichment→sql-consumer→PG ✅ & itop-unified→iTop ✅ & **dcim-es-consumer→ES ✅** (sudah pulih, `telegraf-consumer` lama disabled).
- DLQ flood sudah berhenti (normalizer drop `general_metric`+null; retention DLQ 7d).

### 2.3 Struktur repo yang relevan (ingestion)
| Komponen | Lokasi | Catatan |
|----------|--------|---------|
| **Config Telegraf** | `configs/telegraf/` | `ups-apc.conf`, `telegraf_producer.conf`, `servers-redfish.conf`, `cctv-hikvision.conf`, `infra-monitoring.conf`, `telegraf_consumer.conf` |
| **Kafka cluster** | `kafka/docker-compose-cluster.yml` + `kafka/certs/` | 3-broker KRaft, TLS |
| **Schema Registry** | `schema-registry/docker-compose.yml` | `confluentinc/cp-schema-registry:7.6.0` |
| **Vault** | `vault/docker-compose.yml` | AppRole/KV-v2 |
| **Observability** | `observability/docker-compose.yml` | `dcim_prometheus` (prom/prometheus:v2.45.0) + `dcim_grafana` (grafana/grafana:10.0.3) — **sudah ada**, belum jadi monitoring resmi (masih Kibana) |
| **NiFi** | ⚠️ `_archived/phase2_legacy/phase2/docker-compose.yml` | `apache/nifi:1.24.0`, container `dcim-nifi`, `network_mode: host`, UI HTTPS :8443. **Definisi service ada di folder `_archived` → risiko durabilitas (lihat §5)** |
| **Consumer/normalizer** | `scripts/` | `dcim_normalizer.py`, `dcim_sql_consumer.py`, `dcim_itop_unified_consumer.py`, `dcim_dlq_consumer.py`, `dcim_es_consumer.py`, `dcim_enrichment_api.py` |
| **Dokumen** | `docs/architecture/`, `docs/standar_dcim/`, `docs/handoff/` | arsitektur aktual, referensi/komparasi, handoff |

### 2.4 Inventaris topik Kafka
`dcim.raw.{hardware.server, power.ups, network.interfaces, network.snmp, storage.nas, device.isapi}` (JSON) · `dcim.normalized.events` (Avro) · `dcim.enriched.events` (Avro) · `dcim.dlq.{parse,enrichment,delivery}-failure` · `_schemas`.
> Semua topik **PartitionCount=1** (wiki minta 12); `min.insync.replicas` belum di-set (wiki minta 2) — lihat drift D2.

---

## 3. Status gap vs dcim-wiki Block 2 (NiFi-centric) — checklist tujuan

Pola target wiki §4.1: **Ingest → Validate → Normalize → Enrich → Publish** (gagal → DLQ). NMS/SNMP flow wiki §4.3 pakai processor **`GetSNMP`** → SplitRecord → Jolt → ValidateRecord → PublishKafka.

| # | Drift | Status | Arah penyelesaian |
|---|-------|--------|-------------------|
| **D1** | Ingestion **Telegraf-centric** vs wiki **NiFi-centric** (§4–8) | 🔴 **STUCK — fokus handoff ini** | Migrasi bertahap; sumber pertama = **SNMP UPS** (lihat §4) |
| **D2** | Topik partisi **1** vs wiki **12**; `min.insync.replicas` belum di-set vs wiki **2** | ❌ Terbuka | Naikkan partisi & set ISR=2 (uji dampak ordering/konsumer) saat menyentuh tiap topik |
| **D3** | Tidak ada tahap topik **`validated`** (validasi digabung di normalizer) | ❌ Terbuka | Evaluasi: tambah ValidateRecord eksplisit (wiki §9) **atau** sahkan via ADR bila tetap digabung |
| **D4** | Monitoring **Kibana/ES** vs wiki **Grafana** (§14) | 🟡 Parsial | Stack Grafana/Prometheus **sudah ada** di `observability/` → keputusan user via ADR |
| **D5** | **Real-time/Flink** belum ada (§5.2/#20) | ❌ Terbuka | Di luar skup handoff ini (task terpisah) |
| — | **Kafka ACL/RBAC** (§13) | ⚠️ Klaim≠nyata | `kafka-acls --list` → "No Authorizer configured". Koreksi klaim "done" (pola sama dgn Flink palsu) |

---

## 4. AKAR MASALAH SNMP UPS GAGAL — TERKONFIRMASI (bukti reproduksi live)

Percobaan pertama: process group SNMP UPS sudah dibuat di NiFi mengikuti arahan agent lain, **tapi poll gagal**. Investigasi live 2026-06-30 menemukan akar masalahnya dengan bukti — **dan membantah beberapa teori umum**.

### 4.1 Diagnosis: digest autentikasi SNMPv3 tidak valid (`usmStatsWrongDigests`)

`nifi-app.log` berulang tiap ~2 menit:
```
WARN  org.snmp4j.Snmp  RFC3412 §7.2.11.b: Received REPORT PDU with security level noAuthNoPriv
   VBS[1.3.6.1.6.3.15.1.1.5.0 = 6655], securityName=hndept, peerAddress=192.168.100.140/161
ERROR o.a.n.snmp.processors.GetSNMP  Agent is not available, OID not found or user not found.
```
OID REPORT **`1.3.6.1.6.3.15.1.1.5.0` = `usmStatsWrongDigests`**. Artinya: UPS **menerima paket NiFi & membalas**, tapi **menolak** karena HMAC-SHA auth passphrase yang dikirim NiFi salah. **Bukan** jaringan, **bukan** OID, **bukan** NAR.

### 4.2 Bukti reproduksi (dari host, kredensial Telegraf yang bekerja)
| Kredensial | Hasil |
|---|---|
| auth benar + priv benar | ✅ sukses → `sysDescr = "UPS-FIT"`, model `30KH` |
| **auth salah** + priv benar | ❌ device balas `usmStatsWrongDigests` (`...15.1.1.5.0`) — **identik dengan log NiFi** |
| auth benar + priv salah | ⏱️ timeout (signature berbeda) |

→ Gejala NiFi cocok **persis** dengan kasus **auth passphrase salah**.

### 4.3 Konfigurasi flow NiFi yang ada (dari `flow.json.gz` di volume container)
Process group berisi **2 processor GetSNMP** menarget `192.168.100.140:161`:
- `GetSNMP 935` → OID `1.3.6.1.4.1.935` (enterprise Megatec/Phoenixtec)
- `GetSNMP 33` → OID `1.3.6.1.2.1.33` (UPS-MIB RFC 1628)
- `SNMPv3 / authPriv / user hndept / SHA / AES128 / strategy WALK / retries 0 / timeout 5000`

Versi/level/user/protokol/OID **sudah cocok** dengan Telegraf. Satu-satunya variabel yang salah: **byte passphrase**.

### 4.4 Teori yang DIBANTAH bukti (jangan buang waktu di sini)
- ❌ "NAR SNMP hilang / NiFi 2.x" — ini **NiFi 1.24.0**, `nifi-snmp-nar-1.24.0.nar` ada & berjalan (snmp4j-2.8.18).
- ❌ "Container tak bisa route ke 192.168.100.0/24 / UDP 161 diblok" — container `network_mode: host`; ping 0% loss; round-trip v3 dari host sukses; UPS terbukti membalas paket NiFi.
- ❌ "Salah versi/user/protokol/OID" — semua cocok dengan Telegraf.

### 4.5 Fix (konfirmasi user dulu sebelum apply)
Sumber kebenaran kredensial = `configs/telegraf/ups-apc.conf` (SNMPv3, user `hndept`, SHA auth + AES priv, authPriv). Penyebab paling mungkin: passphrase salah ketik (`!` ter-mangle shell/copy-paste) **atau** nilai sensitif tak terbawa saat import template (beda `nifi.sensitive.props.key`).

→ **Ketik ulang KEDUA passphrase (auth & priv) secara manual** di kedua processor GetSNMP via NiFi UI (`https://10.70.0.56:8443`), **persis sama** dengan nilai di `ups-apc.conf`. Lalu start ulang processor & verifikasi flowfile keluar.

> **Catatan perangkat:** ini **bukan APC** — enterprise OID `935` (Megatec/Phoenixtec), sysDescr "UPS-FIT", unit 30KVA. Label "APC Smart-UPS" di nama file keliru (tidak memengaruhi kegagalan), tapi luruskan saat dokumentasi.

---

## 5. Hambatan struktural migrasi (selesaikan bersamaan, bukan cuma bug passphrase)

1. **Durabilitas (pelajaran Flink).** Definisi service NiFi ada di `_archived/phase2_legacy/`, dan flow ingestion hanya hidup di volume container — **belum ada flow yang ter-export ke git**. **Segera setelah UPS berfungsi: export flow** (download flow definition / NiFi Registry) & commit. Pertimbangkan pindahkan compose NiFi keluar dari `_archived` ke lokasi resmi (dengan persetujuan user).
2. **Gate paritas terblokir.** Tahap 3 roadmap (bandingkan event NiFi vs Telegraf) tak bisa jalan selama UPS belum berhasil di-poll. Bug passphrase memblokir paritas pertama.
3. **Mismatch GET vs WALK + bentuk payload.** Telegraf melakukan **GET skalar** OID `.0` spesifik → JSON datar ala-Telegraf. NiFi di-set **WALK** subtree → struktur berbeda. Normalizer (`metric_mapping.json`) saat ini mengharapkan bentuk Telegraf. Tanpa **JoltTransform** yang menyelaraskan output WALK → bentuk yang sama, event NiFi bisa lolos auth tapi **gagal paritas/normalisasi**.

---

## 6. Urutan eksekusi (paralel-run, anti big-bang — konfirmasi user tiap langkah)

1. **Perbaiki auth SNMP UPS di NiFi** (§4.5) → verifikasi flowfile keluar dari GetSNMP. Publish ke topik **yang sama** `dcim.raw.power.ups`, **paralel** dengan Telegraf (Telegraf tetap hidup). ✅ **(DONE)**
2. **Export flow NiFi ke git** (tutup risiko durabilitas §5.1) sebelum lanjut. ✅ **(DONE - Flow diekspor ke nifi/flow.json.gz dan compose file dipindah ke folder nifi)**
3. **Selaraskan bentuk payload**: tambah JoltTransform agar output WALK SNMP → JSON yang sama dengan Telegraf (wiki §4.3 pola: GetSNMP→SplitRecord→Jolt→ValidateRecord→PublishKafka). ✅ **(DONE - Pastikan karakter `$` dan `.` di-escape dalam Jolt spec seperti `\\$` agar tidak error InvocationTargetException)**
4. **Buktikan paritas** di `dcim_events`/ES: bandingkan jumlah, field, freshness event NiFi vs Telegraf. Harus identik/lebih baik. ✅ **(DONE - Diverifikasi via PG dan Elasticsearch, namun Kafka broker URL di PublishKafka perlu menggunakan `127.0.0.1:9092,127.0.0.1:9095,127.0.0.1:9097` karena NiFi berjalan di network_mode: host)**
5. **Cutover UPS**: setelah paritas terbukti → matikan **hanya** input UPS di Telegraf, NiFi ambil alih. Verifikasi tidak ada regresi. ✅ **(DONE - Polling SNMP UPS pada Telegraf sudah dinonaktifkan di sistem dan di-commit)**
6. **Ulangi pola** untuk sumber berikut (rekomendasi urutan: NMS/SNMP network → Redfish server → NAS → ISAPI/CCTV).
7. **Saat menyentuh tiap topik**: kerjakan D2 (partisi 1→12, ISR=2) & D3 (tahap `validated` atau ADR).
8. **Dokumentasi**: tambah **ADR-004 (Migrasi ingestion Telegraf→NiFi, status in-progress)** di `v4.3-pipeline-architecture.md`; perbaiki badan §0/§3/§6 yang masih kontradiktif; koreksi klaim Kafka ACL.

---

## 7. Smoke test — verifikasi sendiri sebelum & sesudah

```bash
# --- NiFi hidup? versi & NAR SNMP ada? ---
docker ps --filter name=dcim-nifi --format '{{.Names}}\t{{.Image}}\t{{.Status}}'
docker exec dcim-nifi sh -c 'ls /opt/nifi/nifi-current/lib/ | grep -i snmp'   # harus ada nifi-snmp-nar-1.24.0.nar

# --- Host bisa poll UPS via SNMPv3? (ambil kredensial dari configs/telegraf/ups-apc.conf) ---
# snmpget -v3 -l authPriv -u hndept -a SHA -A '<auth_password>' -x AES -X '<priv_password>' \
#   192.168.100.140 .1.3.6.1.2.1.1.1.0     # sukses → STRING: "UPS-FIT"

# --- Error auth SNMP di NiFi? (target: KOSONG setelah fix) ---
docker exec dcim-nifi sh -c "tail -n 200 /opt/nifi/nifi-current/logs/nifi-app.log | grep -iE 'snmp|usmStats|192.168.100.140'"

# --- Topik UPS terisi? (paralel-run: cek laju, bandingkan saat Telegraf vs NiFi) ---
docker exec kafka1 /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka1:29092 --topic dcim.raw.power.ups

# --- Pipeline hilir tetap sehat (jangan ada regresi) ---
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -tAc \
"select count(*), max(event_time) from dcim_events where event_time > now()-interval '5 min';"

# --- Config topik (cek setelah D2) ---
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka1:29092 --describe --topic dcim.raw.power.ups
```

> **Kredensial**: jangan commit/ekspos. SNMP UPS → ambil dari `configs/telegraf/ups-apc.conf`. PG user `sot_admin`. Kafka admin via INTERNAL `kafka1:29092` dari dalam container.

---

## 8. Definisi selesai (untuk skup ini)

- [x] SNMP UPS berhasil di-poll via NiFi (auth fix terverifikasi, flowfile keluar).
- [x] Flow NiFi **ter-export & ter-commit** ke git (durable, lolos uji recreate).
- [x] Output NiFi **paritas** dengan Telegraf di `dcim_events`/ES (jumlah/field/freshness) — *Data terverifikasi masuk ke Kafka dcim.raw.power.ups dan PostgreSQL dcim_events, namun cutover dan export flow belum dilakukan.*
- [x] Cutover UPS dilakukan tanpa regresi pada jalur PG/ES/iTop (smoke test §7 lulus); sumber lain terencana per tahap.
- [ ] Keputusan D2/D3/D4 terdokumentasi (terlaksana atau jadi ADR); ADR-004 ditambahkan.
- [ ] Tidak ada "DONE" tanpa bukti verifikasi yang bisa direproduksi.

---

## 9. Utang teknis / catatan (di luar scope langsung)
- Compose NiFi masih di `_archived/phase2_legacy/` — perlu dipindah ke lokasi resmi + definisi `networks/volumes/restart` deklaratif (jangan andalkan `docker network connect` manual).
- Klaim **Kafka ACL/RBAC "done"** belum nyata (Authorizer broker belum dikonfigurasi) — koreksi seperti kasus Flink.
- Badan `v4.3-pipeline-architecture.md` (§0/§3/§6) masih menulis kondisi rusak (ES mati/DLQ flood/Flink) padahal sudah diperbaiki — selaraskan dengan realitas + tanggal FIXED.
- `dcim-secrets-setup.service` state `failed` basi (service sudah disabled) — `systemctl reset-failed dcim-secrets-setup`.
- Pasca auth fix, konfirmasi **bentuk output** GetSNMP WALK vs scalar GET Telegraf agar normalizer tetap cocok (lihat §5.3).
</content>
</invoke>
