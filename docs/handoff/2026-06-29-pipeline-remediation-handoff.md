# Handoff — Remediation Pipeline v4.3 (2026-06-29)

> **Untuk**: agent/engineer yang akan mengeksekusi perbaikan pipeline. **Dari**: sesi analisis gap & verifikasi live (2026-06-29).
> **Host**: `srv-rnd-dcim` (10.70.0.56) · **Repo**: `/home/infra/dcim_metrics_project` · branch `main`.
> **WAJIB baca dulu, berurutan:**
> 1. `docs/architecture/v4.3-pipeline-architecture.md` — **sumber kebenaran arsitektur aktual** (menggantikan v4.2 yang usang).
> 2. `docs/architecture/v4.3-remediation-plan.md` — rencana perbaikan berprioritas (ini yang Anda eksekusi).
> 3. `/home/infra/dcim-wiki/reference-designs/block2-data-ingestion-integration.md` — **referensi utama** desain (user mengunci ini sebagai acuan alignment).
> 4. Handoff sebelumnya: `docs/handoff/2026-06-22-ai-integration-and-docs-handoff.md` (konteks AI-data-provider).

---

## 0. JANGAN langsung eksekusi — pahami konteks dulu

Dokumen ini sengaja menahan Anda dari "langsung benerin". Sesi sebelumnya gagal **justru karena** eksekusi tanpa durabilitas (lihat kasus Flink di §3). Sebelum menyentuh sistem:
1. Baca 4 dokumen di header.
2. Jalankan **smoke test §6** untuk mengonfirmasi sendiri kondisi live (jangan percaya dokumen buta — verifikasi).
3. Setiap aksi operasional (systemd/docker/broker/config) menyentuh **PRODUKSI** → **konfirmasi user sebelum eksekusi**. User secara eksplisit ingin diminta persetujuan dulu.

---

## 1. Konteks & keputusan yang DIKUNCI user

1. **`/home/infra/dcim-wiki` adalah referensi utama implementasi.** Tujuan akhir: menyelaraskan implementasi aktual dengan dcim-wiki (Block 2). Setiap perubahan dinilai terhadap acuan ini.
2. **Host = penyedia data, bukan tempat menjalankan AI.** Tidak ada inference/model AI on-host (lihat handoff 2026-06-22 §2).
3. **Avro + Schema Registry** dan penamaan topik `dcim.raw/.normalized/.enriched` adalah **keputusan desain yang sah** (lebih kuat dari JSON Schema wiki / pola Modified Kappa). **Jangan** "mengembalikan" ke JSON Schema — cukup dokumentasikan sebagai deviasi sadar.
4. **Jejak versi terpisah & auditable.** Dokumen baru = `v4.3`, jangan ubah v4.0/v4.1/v4.2 (arsipkan/tandai SUPERSEDED saja).
5. Staging git **selektif per-file** — repo punya banyak perubahan working-tree warisan agent lain yang **tidak** boleh ikut ter-commit.

---

## 2. Ringkasan kondisi aktual (terverifikasi live 2026-06-29)

### Yang SEHAT ✅ — jangan diutak-atik
- **Kafka 3-broker** (`kafka1/2/3`, KRaft, TLS :9094, INTERNAL :29092, RF=3) — Up 3 hari.
- **Schema Registry** + **Vault** (AppRole/KV-v2) — Up.
- **PostgreSQL 15.18** (`dcim_sot_postgres`, db `dcim_sot`, user `sot_admin`): `dcim_events` 4,5 jt baris, terkini **2026-06-29 03:59** (segar); `dcim_lineage` 3,16 jt baris (lineage aktif).
- Jalur: Telegraf→raw(JSON) → normalizer→Avro → enrichment→Avro → **sql-consumer→PostgreSQL** ✅ dan **itop-unified→iTop** ✅.

### Yang RUSAK ❌ — target perbaikan
| # | Masalah | Bukti live |
|---|---------|-----------|
| P0-1 | **Jalur Elasticsearch MATI** | `telegraf-consumer.service` error `invalid character '\x00'` terus-menerus (baca Avro sbg JSON). Dok ES terakhir **2026-06-25T07:42Z** (4 hari mati). ES versi **9.3.1**. Ada indeks sampah `dcim-metrics-unified-2227.*` (0 dok). |
| P0-2 | **Flink TIDAK ADA** (klaim palsu) | Diklaim "COMPLETED/RUNNING" di `task.md` agent. Nyata: `flink_alerter.py` tidak ada di mana pun, tidak pernah masuk git, 0 container Flink, tidak ada kode PyFlink. Hanya tersisa `flink/Dockerfile` + `docker-compose.yml` generik (tanpa `networks`/checkpoint/submit). |
| P1-1 | **DLQ delivery-failure membanjir** | `dcim.dlq.delivery-failure` = **3,98 jt**, tumbuh **~30/dtk** (~2,6 jt/hari). Didominasi event NAS/interface `metric_value: null` + `metric_name=general_metric`. |
| P1-2 | **Threshold alerter baca ES mati** | `dcim-threshold-alerter.service` active tapi sumbernya ES dark → alarm "Device Not Reporting" palsu. |
| P2-1 | **Service systemd `failed`** | `dcim-server-inventory` (Redfish→Kafka), `dcim-secrets-setup` (RAM secrets), `dcim-itop-ralph-sync`. |

### Inventaris topik Kafka (acuan)
`dcim.raw.{hardware.server, power.ups, network.interfaces, network.snmp, storage.nas, device.isapi}` (JSON) · `dcim.normalized.events` (Avro) · `dcim.enriched.events` (Avro) · `dcim.dlq.{parse,enrichment,delivery}-failure` (JSON) · `_schemas`.
> **Batas Avro = `dcim.normalized.events`.** Consumer apa pun yang membaca `.normalized`/`.enriched` WAJIB deserialize Avro (magic byte `0x00` + schema id). Ini akar P0-1.

---

## 3. Pelajaran dari kegagalan Flink (BACA sebelum mengerjakan P0-2)

Agent sebelumnya melaporkan Flink "selesai & RUNNING" padahal **tidak ada bekasnya**. Penyebab: pekerjaannya **ephemeral** — file dibuat di container/working-dir & network disambung manual (`docker network connect kafka_default`), lalu **hilang** saat cluster Kafka di-recreate karena `flink/docker-compose.yml` **tidak punya** section `networks`.

**Aturan untuk Anda:** apa pun yang Anda buat harus **durable & ter-commit**:
- Kode → masuk git (bukan hanya di container).
- Container → definisikan `networks`, `volumes` (checkpoint), `restart: unless-stopped` **secara deklaratif** di compose; jangan andalkan `docker network connect` manual.
- Uji durabilitas: `docker compose down && up` lalu pastikan job tetap hidup.
- Jangan tandai "DONE" tanpa bukti verifikasi yang bisa direproduksi.

---

## 4. Urutan eksekusi yang disarankan (detail di `v4.3-remediation-plan.md`)

> Konfirmasi user sebelum tiap langkah. Lakukan satu per satu + verifikasi.

1. **P1-1 — Hentikan banjir DLQ** (paling cepat menurunkan beban/noise): filter event `metric_value IS NULL`+`general_metric` di hulu (normalizer/consumer), perbaiki mapping SNMP NAS/interfaces, set `retention.ms` topik DLQ, drain pesan lama setelah penyebab berhenti.
2. **P0-1 — Hidupkan ES**: ganti `telegraf-consumer` (json) dengan **consumer Avro Python** (pola `dcim-sql-consumer`) → bulk-index ke ES dengan `@timestamp` benar; buat `dcim-es-consumer.service`; hapus indeks sampah `dcim-metrics-unified-2227.*`. (Opsi cepat sementara: arahkan telegraf ke topik JSON, tapi kehilangan field enrichment.)
3. **P1-2 — Sumber alerter**: setelah P0-1 sembuh otomatis; ATAU alihkan threshold alerter baca **PostgreSQL** `dcim_events` (selalu segar) agar tak bergantung ES.
4. **P2-1 — Service failed**: pulihkan `dcim-server-inventory`, `dcim-secrets-setup` (verifikasi konsumen baca dari Vault, bukan `/run/secrets/dcim/`), `dcim-itop-ralph-sync`.
5. **P0-2 — Flink**: rekomendasi **Opsi B dulu** (hapus `flink/`, koreksi `task.md`/walkthrough agent jadi "NOT IMPLEMENTED", catat sbg keputusan sadar). **Opsi A** (implementasi nyata) terjadwal: consume `dcim.enriched.events` (Avro), output ke topik **ber-consumer nyata** (bukan `dcim.alerts.p1` dead-end), compose deklaratif + checkpoint.
6. **P2-2 — Dokumentasi**: arsipkan v4.2 (SUPERSEDED→v4.3), catat drift versi (PG 15.18, ES 9.3.1), dokumentasikan deviasi Avro & penamaan topik sbg keputusan arsitektur.

---

## 5. Status alignment vs dcim-wiki (Block 2) — sebagai checklist tujuan

| Kriteria | Status | Aksi |
|----------|--------|------|
| Kafka HA RF=3, TLS | ✅ sejalan | — |
| Vault secrets | ✅ (tapi `secrets-setup` failed) | P2-1 |
| Data lineage | ✅ sejalan | — |
| Enrichment (NiFi/CMDB) | ✅ (NiFi processor Avro set manual via GUI) | verifikasi NiFi |
| DLQ | ⚠️ ada tapi banjir | P1-1 |
| **Real-time processing (Flink)** | ❌ tidak ada | P0-2 |
| **Observability sink (ES)** | ❌ mati | P0-1 |
| Schema (Avro vs JSON Schema wiki) | ⚠️ deviasi sah | P2-2 (dokumentasikan) |
| Penamaan topik (`dcim.raw.*` vs `dcim.events.*`) | ⚠️ deviasi sah | P2-2 (dokumentasikan) |
| RBAC/Kafka ACL | ⚠️ diklaim selesai, belum diverifikasi | verifikasi terpisah |

---

## 6. Smoke test — verifikasi sendiri sebelum & sesudah perbaikan

```bash
# --- PostgreSQL: pipeline hidup? (harus segar < 5 menit) ---
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -tAc \
"select count(*), max(event_time) from dcim_events where event_time > now()-interval '5 min';"

# --- ES: hidup lagi? (P0-1) — harus muncul dok hari ini ---
curl -sk -u 'elastic:C+H+pFb*aIAqWcOo-X8q' \
 "https://10.70.0.56:9200/dcim-metrics-unified*/_search?size=0" \
 -H 'Content-Type: application/json' \
 -d '{"aggs":{"m":{"max":{"field":"@timestamp"}}}}' | grep -o '"value_as_string":"[^"]*"'
# --- ES error masih ada? (harus KOSONG setelah fix) ---
journalctl -u telegraf-consumer.service -n 20 --no-pager | grep '\\x00'

# --- DLQ delivery-failure: laju pertumbuhan (P1-1) — target ~0 ---
a=$(docker exec kafka1 /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka1:29092 --topic dcim.dlq.delivery-failure | awk -F: '{print $3}'); sleep 5; \
b=$(docker exec kafka1 /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka1:29092 --topic dcim.dlq.delivery-failure | awk -F: '{print $3}'); echo "delta_5s=$((b-a))"

# --- Flink: ada container? (P0-2) ---
docker ps -a --filter name=flink --format '{{.Names}}\t{{.Status}}'   # kosong = belum ada

# --- Service yang failed (P2-1) ---
systemctl --failed | grep dcim
```

> **Catatan kredensial:** PostgreSQL user `sot_admin`; ES `elastic` / `C+H+pFb*aIAqWcOo-X8q`. Kafka admin via INTERNAL listener `kafka1:29092` dari dalam container `kafka1` (binari di `/opt/kafka/bin/*.sh`). **Jangan** commit kredensial; tangani dengan hati-hati.

---

## 7. Utang teknis / catatan (di luar scope langsung)
- Kredensial hardcoded di beberapa script (ES password di `scripts/dcim_threshold_alerter.py`, dll) — idealnya ke Vault.
- Drift versi: dokumen v4.2 menyebut PG14/ES7, aktual PG15.18/ES9.3.1 — agent sebelumnya menandai upgrade "SKIPPED" tapi versi sudah berbeda; perlu pencatatan resmi (P2-2).
- `dcim-telegraf-consumer` (container docker) sudah Exited 4 minggu — fungsi kini di systemd `telegraf-consumer.service`; bersihkan container mati bila tak dipakai.
- `task.md`/`walkthrough.md` agent di `~/.gemini/antigravity-ide/brain/` berisi klaim Flink yang **tidak akurat** — jangan jadikan acuan kebenaran; acuan adalah `v4.3-pipeline-architecture.md`.
