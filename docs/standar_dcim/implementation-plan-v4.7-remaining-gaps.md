# Implementation Plan — Remaining Gaps v4.7.0 Pipeline Architecture

**Author:** Imam Syauqi Achmad  
**Date:** 2026-08-13  
**Host:** srv-rnd-dcim (10.70.0.56)  

Berdasarkan komparasi v4.7.0 dan dokumen referensi Block 2 DCIM-Wiki, berikut adalah rencana implementasi komprehensif untuk gap fungsional yang tersisa. Rencana ini sudah dipetakan dengan sub-tasks ST-391 hingga ST-394.

---

## 1. ST-391: Virtualization/Cloud Collector (VMware/Proxmox Ingestion Flow)
**Terkait MT-014 (Data Ingestion Pipelines)**  
**Status:** Waiting

### Deskripsi:
Implementasi NiFi flow dan collector untuk data Virtualization / Cloud (VMware vSphere & Proxmox) sesuai spesifikasi Block 2 DCIM-Wiki (Section 4.5).

### Rincian Pengerjaan:
1. **Setup Process Group di NiFi:** Buat Process Group khusus untuk `Virtualization Ingestion`.
2. **Implementasi Proxmox VE API / vCenter REST API Polling:**
   - Gunakan processor `InvokeHTTP` untuk mengambil metrik dari hypervisor.
   - Konfigurasi parameter autentikasi (menggunakan kredensial yang diambil dari HashiCorp Vault melalui `src/utils/secrets.py`).
3. **Data Normalization:**
   - Tambahkan processor `JoltTransformJSON` dengan spesifikasi `vm-normalize.jolt`.
   - Pastikan field hasil normalisasi memuat `hostname`, `metrics`, `timestamp`, `resource_type: virtualization`, dll.
4. **Validation & Kafka Publishing:**
   - Tambahkan processor `ValidateRecord` dan konfigurasikan Avro schema `event-schema.avsc` (menggunakan Confluent Schema Registry).
   - Tambahkan processor `PublishKafka_2_0` untuk publish ke topic `dcim.events.raw` dengan min.insync.replicas=2.

---

## 2. ST-392: Konektor ITSM (ServiceNow & Jira Integration)
**Terkait MT-014 (Data Ingestion Pipelines)**  
**Status:** Waiting

### Deskripsi:
Implementasi konektor REST API OAuth2/API Key bidirectional untuk ServiceNow dan Jira sebagai bagian integrasi ITSM (Block 2 DCIM-Wiki Section 9).

### Rincian Pengerjaan:
1. **ServiceNow Integration (`src/connectors/itsm/servicenow.py`):**
   - Implementasi `ServiceNowConnector` menggunakan protokol REST API + OAuth2.
   - Fungsi `transform_to_dcim()`: Ubah ServiceNow incident menjadi DCIM event (untuk status tracking).
   - Fungsi `create_ticket()`: Petakan DCIM alert event (criticality/severity yang telah di-score) menjadi ServiceNow Incident.
2. **Jira Integration (`src/connectors/itsm/jira.py`):**
   - Implementasi `JiraConnector` menggunakan protokol REST API + API Key.
   - Mapping alert events menjadi Jira Issues untuk tim Facilities atau IT Operations.
3. **Konfigurasi Autentikasi:**
   - Tambahkan token OAuth2 dan API Key ke dalam HashiCorp Vault.
   - Update config loader untuk pull secret ITSM.
4. **Integrasi ke Enrichment Flow:**
   - Panggil konektor secara asynchronous / via Kafka event topic saat alert rules Prometheus (atau Block 7) melepaskan notifikasi yang memenuhi threshold insiden.

---

## 3. ST-393: S3/MinIO Cold Storage Archiving Pipeline
**Terkait MT-014 (Data Ingestion Pipelines)**  
**Status:** Waiting

### Deskripsi:
Implementasi NiFi flow `PutS3Object` untuk pengarsipan pesan Dead Letter Queue (DLQ) dan retention jangka panjang data telemetri ke S3/MinIO.

### Rincian Pengerjaan:
1. **Persiapan S3/MinIO Object Storage:**
   - Setup MinIO bucket lokal (untuk dev/staging) atau integrasi ke mock AWS S3.
   - Bucket target: `dcim-dlq-archive` dan `dcim-telemetry-archive`.
   - Update credential S3 di HashiCorp Vault.
2. **DLQ Archiving Flow (NiFi):**
   - Buat routing tambahan di akhir rute DLQ saat ini (`delivery-failure`, `enrichment-failure`, `parse-failure`).
   - Gunakan processor `MergeContent` (batching pesan yang gagal) dilanjutkan dengan `PutS3Object` (bucket `dcim-dlq-archive`).
3. **Telemetry Long-term Retention:**
   - Buat consumer group baru di Kafka: `dcim_s3_archive_consumer`.
   - Subscribe ke topic `dcim.events.raw` dan `dcim.enriched.events`.
   - Batching message setiap jam / setiap 1GB (sesuai SLA wiki) lalu lempar ke bucket `dcim-telemetry-archive`.

---

## 4. ST-394: End-to-End Integration Testing & Performance Load Test
**Terkait MT-040 (Integration Testing)**  
**Status:** Waiting

### Deskripsi:
Pengujian end-to-end pipeline (target 430 eps sustained, latency p99 < 1s) dan verifikasi seluruh acceptance criteria untuk menyatakan Block 2 dari DCIM-Wiki berstatus DONE 100%.

### Rincian Pengerjaan:
1. **Load Generation & Stress Testing:**
   - Gunakan synthetic metric generator atau Locust/JMeter untuk memborbardir telemetry ingestion endpoints / Kafka topics.
   - Sustain traffic di 430+ events per second (eps) selama 1 jam.
2. **Verifikasi Latency (p99 < 1s):**
   - Gunakan Grafana monitoring dashboard yang telah ada.
   - Pastikan processing delay di NiFi dan Normalization script (end-to-end dari `raw` hingga Elasticsearch/TimescaleDB) tidak lebih dari 1 detik di persentil 99 (p99).
3. **Verifikasi Quality Gates:**
   - Validasi bahwa payload yang disengaja cacat (missing fields, wrong schema) tertolak dan masuk ke `dcim-dlq-archive`.
   - Validasi bahwa deduplication checker (Redis) berfungsi maksimal saat load tinggi.
4. **Final Checklist & Sign-off:**
   - Cek semua item pada Section 15 (Acceptance Criteria) dari `block2-data-ingestion-integration.md`.
   - Jika pass, tutup MT-014 dan MT-040 untuk komponen Block 2.

