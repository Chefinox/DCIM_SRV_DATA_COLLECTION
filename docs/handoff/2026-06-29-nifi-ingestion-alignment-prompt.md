# Prompt Eksekusi — Penyelarasan Data Ingestion ke Referensi dcim-wiki

> Salin seluruh blok di bawah sebagai prompt awal untuk agent pelaksana.

---

## PERAN & TUJUAN

Kamu adalah engineer yang mengerjakan penyelarasan pipeline DCIM agar **arsitektur data ingestion** sesuai referensi utama di `/home/infra/dcim-wiki`. Host: `srv-rnd-dcim` (10.70.0.56), repo: `/home/infra/dcim_metrics_project`, branch `main`. Ini sistem **PRODUKSI** — tidak ada perubahan operasional tanpa persetujuan user.

**Keputusan arah yang DIKUNCI user:**
- Implementasi saat ini **Telegraf-centric** (Telegraf langsung produce ke Kafka). Ini implementasi lama dan **akan disesuaikan untuk mengikuti arsitektur data ingestion di dcim-wiki**, yaitu pola **NiFi-centric** (NiFi sebagai flow ingestion: terima → validasi → publish ke Kafka), sesuai `reference-designs/block2-data-ingestion-integration.md` §4–8.
- dcim-wiki adalah **referensi utama**. Tujuan akhir: menutup drift arsitektur ingestion antara implementasi aktual dan wiki.

## WAJIB BACA DULU (berurutan) — JANGAN eksekusi sebelum paham

1. `docs/handoff/2026-06-29-pipeline-remediation-handoff.md` — konteks & aturan kerja.
2. `docs/architecture/v4.3-pipeline-architecture.md` — arsitektur aktual + ADR-001/002/003.
3. `docs/architecture/v4.3-remediation-plan.md` — rencana perbaikan.
4. `/home/infra/dcim-wiki/reference-designs/block2-data-ingestion-integration.md` — **referensi target**, fokus:
   - §3.x Topik Kafka (10 topik, 12 partisi, RF=3, min.insync=2, pola `dcim.events.{raw,validated,enriched,dlq}`)
   - §4–8 Flow NiFi (BMS, NMS, Server/Storage, Cloud/VM, Access Control)
   - §9 Validation processor, §10 Enrichment, §11 DLQ, §12 Lineage
   - §15 Acceptance Criteria (20 kriteria)
   - §17 NVR connector flows

## KONDISI AKTUAL (terverifikasi live 2026-06-29 — verifikasi ulang sendiri sebelum mulai)

**SEHAT — jangan dirusak:**
- Kafka 3-broker (kafka1/2/3, KRaft, TLS :9094, INTERNAL :29092, RF=3), Schema Registry, Vault — Up.
- PostgreSQL 15.18 (`dcim_sot`, user `sot_admin`): `dcim_events` segar (≤5 mnt), `dcim_lineage` aktif.
- Jalur Avro: normalizer→`dcim.normalized.events`→enrichment→`dcim.enriched.events`→sql-consumer→PG ✅ & itop-unified→iTop ✅.
- **ES sudah PULIH** via `dcim-es-consumer.service` (Avro→ES, sudah benar). `telegraf-consumer` lama sudah disabled.
- DLQ flood sudah berhenti (normalizer drop `general_metric`+null; retention DLQ 7d).

**Ingestion saat ini (yang akan diubah):**
- `telegraf.service` produce langsung ke 6 topik `dcim.raw.*` (hardware.server, power.ups, network.interfaces, network.snmp, storage.nas, device.isapi) format JSON.
- NiFi (`dcim-nifi`) saat ini **hanya** dipakai di tahap enrichment, BUKAN ingestion.

## DRIFT vs dcim-wiki yang harus ditangani (skup pekerjaan)

| # | Drift | Arah penyelesaian |
|---|-------|-------------------|
| D1 | **Ingestion Telegraf-centric** vs wiki **NiFi-centric** (§4–8) | **Migrasikan ingestion ke NiFi** secara bertahap & paralel-run (lihat Tahapan) |
| D2 | Topik partisi=**1** vs wiki **12**; `min.insync.replicas` tidak di-set vs wiki **2** | Naikkan partisi & set `min.insync.replicas=2` (uji dampak ordering/konsumer) |
| D3 | Tidak ada tahap topik `validated` (validasi digabung ke normalizer) | Evaluasi: tambah tahap validasi eksplisit sesuai wiki §9, atau dokumentasikan sbg ADR bila tetap digabung |
| D4 | Monitoring **Kibana/ES** vs wiki **Grafana** (#19) | Keputusan user: pertahankan Kibana (buat ADR) atau tambah Grafana |
| D5 | **Real-time/Flink belum ada** (#20) | Di luar skup prompt ini — task terpisah (Opsi A di remediation plan) |

> **Catatan deviasi yang SUDAH disahkan (JANGAN diubah tanpa instruksi):** Avro+Schema Registry (ADR-001), penamaan topik `dcim.raw/.normalized/.enriched` (ADR-002), versi PG15.18/ES9.3.1 (ADR-003), konektor iTop/Ralph (bukan ServiceNow/SAP). Untuk D1, **selaraskan POLA arsitektur (NiFi sebagai ingestion + tahap validasi)**, sambil **mempertahankan** konvensi Avro & namespace topik yang sudah jadi standar kita — kecuali user memutuskan lain.

## TAHAPAN KERJA (paralel-run, anti big-bang)

Migrasi Telegraf→NiFi tidak boleh memutus jalur PG/ES/iTop yang sehat. Lakukan bertahap:

1. **Discovery & desain.** Petakan tiap input Telegraf (Redfish/SNMP/ISAPI/SSH/NAS) ke flow NiFi padanannya (wiki §4–8 + §17 NVR). Hasilkan dokumen desain + daftar processor NiFi per sumber. **Minta persetujuan user sebelum lanjut.**
2. **Bangun flow NiFi untuk SATU sumber dulu** (rekomendasi: yang paling sederhana, mis. UPS/SNMP) → publish ke topik raw yang sama. Jalankan **paralel** dengan Telegraf (jangan matikan Telegraf dulu).
3. **Validasi paritas data**: bandingkan event dari NiFi vs Telegraf di `dcim_events`/ES (jumlah, field, freshness). Pastikan identik/lebih baik.
4. **Cutover per sumber**: setelah paritas terbukti, matikan input Telegraf untuk sumber itu, NiFi ambil alih. Ulangi untuk sumber berikutnya.
5. **Tahap validasi (D3)** & **config topik (D2)** dikerjakan saat menyentuh tiap topik.
6. **Dokumentasi**: setiap keputusan jadi ADR di `v4.3-pipeline-architecture.md`.

## PERBAIKAN DOKUMEN (kerjakan lebih dulu — cepat & penting)

`v4.3-pipeline-architecture.md` saat ini **kontradiktif**: §0/§3/§6 masih menulis "ES MATI / DLQ flood 3,98 jt / klaim Flink" seolah kondisi sekarang, padahal **sudah diperbaiki** (lihat ADR §7 + realitas). 
- Perbarui §0, §3, §6 agar mencerminkan **kondisi pasca-remediasi** (tandai item FIXED + tanggal, jangan hapus jejak histori — boleh pakai kolom "Status sebelum → sesudah").
- Tambah ADR baru: **ADR-004 Migrasi ingestion Telegraf→NiFi** (keputusan, alasan, dampak, status: in-progress).
- Bersihkan: `systemctl reset-failed dcim-secrets-setup` (state failed basi; service sudah disabled).

## ATURAN (WAJIB)

- **Konfirmasi user sebelum setiap aksi operasional** (NiFi flow baru, matikan Telegraf, ubah partisi topik, dll). Tampilkan rencana, tunggu persetujuan.
- **Durabilitas**: semua artefak (flow NiFi → export template/registry, config, kode) **ter-commit ke git**, jangan ephemeral. (Pelajaran kasus Flink: kerja yang tidak persisten = hilang saat container recreate.)
- **Jangan sentuh** jalur sehat (PG/ES/iTop/normalizer/enrichment) sampai pengganti NiFi terbukti paritas.
- **Staging git selektif per-file** — repo punya banyak perubahan working-tree warisan; jangan commit massal.
- Jangan tandai "DONE" tanpa bukti verifikasi yang bisa direproduksi.
- Jaga kredensial (PG `sot_admin`, ES `elastic`, dll) — jangan commit/ekspos.

## SMOKE TEST (verifikasi sebelum & sesudah)

```bash
# Pipeline segar:
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -tAc \
"select count(*), max(event_time) from dcim_events where event_time > now()-interval '5 min';"
# ES segar:
curl -sk -u 'elastic:C+H+pFb*aIAqWcOo-X8q' "https://10.70.0.56:9200/dcim-metrics-unified*/_count" \
 -H 'Content-Type: application/json' -d '{"query":{"range":{"@timestamp":{"gte":"now-15m"}}}}'
# Topik config (cek partisi/min.insync setelah D2):
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka1:29092 --describe --topic dcim.raw.power.ups
# DLQ tidak banjir lagi:
docker exec kafka1 /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka1:29092 --topic dcim.dlq.delivery-failure
```

## DEFINISI SELESAI (untuk skup ini)

- [ ] Dokumen v4.3 konsisten dengan realitas pasca-remediasi + ADR-004 ditambahkan.
- [ ] Minimal 1 sumber sudah ingest via NiFi (paralel-run terbukti paritas), sisanya terencana per tahap.
- [ ] Keputusan D2/D3/D4 terdokumentasi (terlaksana atau jadi ADR).
- [ ] Tidak ada regresi pada jalur PG/ES/iTop (smoke test lulus).
- [ ] Semua artefak ter-commit & durable.
