# Standar Klasifikasi Data (Data Classification Matrix) — DCIM Platform v4.5.2

> **Dokumen Standar Resmi:** Standar Tata Kelola & Klasifikasi Keamanan Data  
> **Versi:** 1.0.0  
> **Tanggal:** 24 Juli 2026  
> **Status:** Active / Production Baseline  
> **Referensi Utama:** [dcim-wiki block2 §13.1](file:///home/infra/dcim-wiki/reference-designs/block2-data-ingestion-integration.md#L1206-L1214) • [block3 §8.2](file:///home/infra/dcim-wiki/reference-designs/block3-asset-repository-technical-requirements.md#L445-L453) • [block6 §10.1](file:///home/infra/dcim-wiki/reference-designs/block6-siem-soc.md#L819-L829) • [dcim-core-platform.md](file:///home/infra/dcim-wiki/concepts/dcim-core-platform.md)

---

## 1. Pendahuluan

Dokumen ini mendefinisikan **Data Classification Matrix** untuk seluruh data yang mengalir, diproses, dan disimpan dalam DCIM Pipeline v4.5.2. Penerapan kerangka kerja klasifikasi data ini bertujuan untuk:
- Memastikan asas *Security by Design* dan *Least Privilege* sesuai standar ISO/IEC 27001 & NIST Cybersecurity Framework.
- Memberikan klasifikasi yang jelas untuk setiap aset data dari Layer L1 (Data Sources) hingga Layer L16 (Data Quality).
- Menetapkan persyaratan penanganan teknis (enkripsi transit/at-rest, akses RBAC, audit logging, dan retensi).

---

## 2. 4 Level Klasifikasi Data

Sesuai dengan spesifikasi `dcim-wiki` (Block 2 §13.1 & Block 3 §8.2), data pada platform DCIM dikategorikan ke dalam **4 tingkat kerahasiaan**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATA CLASSIFICATION LEVELS                           │
│                                                                         │
│  🔴 L4 — SECRET        Credentials, Encryption Keys, Passwords, Tokens   │
│  🟧 L3 — RESTRICTED    Security Events, SIEM Alerts, Audit Logs, PII     │
│  🟨 L2 — CONFIDENTIAL  Asset Topology, IP, Hostname, Serial, CMDB CIs  │
│  🟩 L1 — INTERNAL      Telemetry Metrics (CPU, Temp, Power, Fan Speed)   │
└─────────────────────────────────────────────────────────────────────────┘
```

| Level | Label Klasifikasi | Deskripsi & Sensitivitas | Contoh Data Aktual di Pipeline |
|-------|-------------------|--------------------------|--------------------------------|
| **L1** | `INTERNAL` | Data operasional telemetri biasa. Kebocoran data tidak berdampak kritis pada keamanan fisik/cyber infrastruktur. | Metrik suhu fan, penggunaan CPU (%), penggunaan memori (%), tegangan UPS (V), disk temperature, uptime, SNMP interface counters. |
| **L2** | `CONFIDENTIAL` | Data konfigurasi & inventaris aset. Kebocoran data dapat mengungkapkan topologi jaringan dan arsitektur infrastruktur data center. | Hostname (`SERVER-01`, `FIT-Core-SW`), IP address (`10.70.0.56`), Serial Number, MAC Address, Model Hardware, iTop CI relationships, data finansial aset (pembelian/penyusutan). |
| **L3** | `RESTRICTED` | Data kejadian keamanan, log audit, dan metadata pengawasan. Membutuhkan proteksi ketat dengan prinsip *need-to-know*. | SIEM Alerts (Wazuh/Elastalert2 events), login failure logs, event lineage audit trail (`event_lineage` table), metadata CCTV/camera channel, user action history. |
| **L4** | `SECRET` | Kredensial rahasia, kunci enkripsi, dan token otorisasi. Kebocoran data mengakibatkan *total system compromise*. | HashiCorp Vault secrets, password database PostgreSQL/Redis/iTop, API keys (ISAPI CCTV, iTop REST), Kafka SSL certificates (`ca-cert.pem`), Docker secrets. |

---

## 3. Per-Component Classification Map

Tabel berikut memetakan setiap komponen fisik/logis dalam DCIM Pipeline v4.5.2 terhadap tingkat klasifikasi data:

| Komponen Pipeline | Aset Data / Topik / Tabel | Level Klasifikasi | Kontrol Keamanan Aktif saat Ini | Target Level 2 Enforcement |
|-------------------|--------------------------|------------------|--------------------------------|----------------------------|
| **Kafka Broker** | `dcim.raw.*` (Raw metrics) | L1 — Internal | Kafka SSL/TLS (`:9094`) | Kafka ACLs (Write allow per NiFi poller) |
| **Kafka Broker** | `dcim.normalized.events` | L2 — Confidential | Kafka SSL/TLS, Avro Schema Registry | Kafka ACLs (Read allow Normalizer/Consumers) |
| **Kafka Broker** | `dcim.siem.alerts` | L3 — Restricted | Kafka SSL/TLS | Kafka ACLs (Dedicated consumer group) |
| **Kafka Broker** | `dcim.dlq.*` (Failed events) | L2–L3 — Confid./Restricted | Kafka SSL/TLS | Kafka ACLs (Restricted access to DLQ consumer) |
| **Elasticsearch** | `dcim-metrics-unified-*` | L2 — Confidential | HTTPS (port 9200), HTTP Basic Auth (`elastic`) | Kibana Space RBAC (`metrics_viewer`) |
| **Elasticsearch** | `dcim-siem-*` | L3 — Restricted | HTTPS, Restricted Index Access | Kibana Space RBAC (`soc_analyst`) |
| **PostgreSQL** | `dcim_sot` (`dlq_records`, `event_lineage`) | L2–L3 — Confid./Restricted | Database network restriction (`10.70.0.56`), `sot_admin` role | Row-Level Security (RLS) pada tabel audit |
| **Redis Cache** | Database `1` (Asset & CI cache) | L2 — Confidential | Localhost binding (`127.0.0.1:6379`) | Redis AUTH / Password protection |
| **iTop CMDB** | Classes: `Server`, `NetworkDevice`, `NAS`, `PowerSource` | L2 — Confidential | HTTP Basic Auth (`admin`), Localhost REST API | HTTPS API endpoint + Token auth |
| **HashiCorp Vault** | Secrets engine (`dcim/secrets/*`) | L4 — Secret | AppRole authentication, Token renewal, Audit log | Vault Transit engine key auto-rotation |
| **Local Configs** | `configs/.env`, `configs/secrets/` | L4 — Secret | File permission `0600`, `.gitignore` enforcement | Vault dynamic secret resolution |
| **Apache NiFi** | Ingestion flow logic & credentials | L3 — Restricted | HTTPS (`:8443`), Certificate authentication | NiFi Fine-Grained Component Policies |
| **Prometheus** | Metric scrapers (`:9100`, `:9187`, `:9121`, `:9308`, `:9114`) | L1 — Internal | Internal network binding | Prometheus Basic Auth |

---

## 4. Persyaratan Penanganan Data (Handling Guidelines)

Tabel berikut menetapkan aturan penanganan teknis wajib untuk setiap tingkat klasifikasi data:

```markdown
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 TECHNICAL HANDLING MATRIX                                            │
├──────────────┬──────────────────┬──────────────────┬──────────────────┬────────────────┬─────────────┤
│ Level        │ Enkripsi Transit │ Enkripsi At-Rest │ Access Control   │ Audit Logging  │ Retensi SLA │
├──────────────┼──────────────────┼──────────────────┼──────────────────┼────────────────┼─────────────┤
│ L1 Internal  │ TLS 1.2+         │ Opsional         │ Network Control  │ Opsional       │ 90 Hari     │
│ L2 Confid.   │ Wajib (TLS 1.2+) │ Direkomendasikan │ RBAC + Auth      │ Wajib          │ 180 Hari    │
│ L3 Restrict. │ Wajib (TLS 1.2+) │ Wajib (AES-256)  │ RBAC + Need-Know │ Wajib (Detailed)│ 365 Hari    │
│ L4 Secret    │ Wajib (mTLS)     │ Wajib (Vault)    │ AppRole / Token  │ Wajib + Alert  │ Dynamic     │
└──────────────┴──────────────────┴──────────────────┴──────────────────┴────────────────┴─────────────┘
```

### Aturan Spesifik:
1. **L1 (Internal):** Data metrik diperbolehkan dikonsumsi oleh tim monitoring dan AI tanpa enkripsi tambahan pada payload, selama berada di dalam network internal terisolasi.
2. **L2 (Confidential):** Data yang memuat Serial Number atau IP wajib menggunakan jalur TLS 1.2+ (seperti Kafka `:9094` SSL). Tidak boleh diekspor ke file publik tanpa anonisasi.
3. **L3 (Restricted):** Log kejadian keamanan (SIEM) dan event lineage wajib disimpan dalam media terenkripsi (AES-256) dengan retensi 365 hari untuk kebutuhan audit compliance.
4. **L4 (Secret):** Kredensial **dilarang keras** ditulis dalam *source code* secara plaintext. Harus selalu mengikuti rantai resolusi `Vault AppRole` -> `Docker Secret` -> `Environment Variable` (sesuai standar MT-018 compliance).

---

## 5. Rencana Kematangan (Maturity Roadmap: Level 1 -> Level 2)

Sesuai panduan `dcim-wiki` (*staging-production-environment.md §9.3*), sistem saat ini telah memenuhi **Level 1 (Basic / Dokumen Standar & Labeling)**. Tahap berikutnya menuju **Level 2 (Full Technical Enforcement)** akan mencakup:

1. **Kafka ACLs:** Menerapkan pembatasan `kafka-acls.sh` untuk memastikan hanya producer/consumer terverifikasi yang dapat membaca/menulis ke topik `dcim.normalized.events` dan `dcim.siem.alerts`.
2. **Redis Authentication:** Menambahkan `requirepass` pada Redis instance untuk melindungi L2 asset cache.
3. **Elasticsearch RBAC Spaces:** Memisahkan index `dcim-metrics-*` (L2) dan `dcim-siem-*` (L3) ke dalam Kibana Spaces terpisah dengan role-based access.

> *Catatan:* Implementasi Level 2 Enforcement teknis di atas akan digabungkan bersama pemenuhan gap **RBAC for Services (P3)** pada sesi mendatang.

---

## 6. Persetujuan & Riwayat Dokumen

| Versi | Tanggal | Penulis | Perubahan | Status |
|-------|---------|---------|-----------|--------|
| 1.0.0 | 2026-07-24 | Tim Infrastruktur FIT | Inisialisasi Data Classification Matrix berbasis DCIM-Wiki | Approved |
