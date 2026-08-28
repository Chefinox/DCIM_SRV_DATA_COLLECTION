# Implementation Plan — Remaining Gaps v4.7.0 Pipeline Architecture

**Author:** Imam Syauqi Achmad  
**Date:** 2026-08-13  
**Host:** srv-rnd-dcim (10.70.0.56)  

Berdasarkan komparasi v4.7.0 dan dokumen referensi Block 2 DCIM-Wiki, berikut adalah rencana implementasi komprehensif untuk gap fungsional yang tersisa. Rencana ini sudah dipetakan dengan sub-tasks ST-391 hingga ST-394.

> **PENGUMUMAN PENTING (PIPELINE READINESS):** 
> Implementasi untuk Virtualisasi (ST-391) dan ITSM (ST-392) saat ini dibangun menggunakan pendekatan **Synthetic Fixture-Replay Adapters (Mock API)**. Tujuannya adalah untuk membuktikan **kesiapan arsitektur (Pipeline Readiness)** dan memastikan *end-to-end pipeline* tetap sehat tanpa terpengaruh oleh ketiadaan akses ke server fisik. Teknisi selanjutnya hanya perlu mengganti URL Endpoint dari Mock API ke server Proxmox/Jira asli saat konektivitas jaringan sudah siap.

---

## 1. ST-391: Virtualization/Cloud Collector (VMware/Proxmox Ingestion Flow)
**Terkait MT-014 (Data Ingestion Pipelines)**  
**Status:** Waiting

### Deskripsi:
Implementasi NiFi flow dan collector untuk data Virtualization / Cloud (VMware vSphere & Proxmox) menggunakan **Mock API / Fixture** untuk readiness.

### Rincian Pengerjaan:
1. **Pembuatan Mock API (Fixture):** Buat script Python lokal untuk mensimulasikan respon Proxmox VE API.
2. **Setup Process Group di NiFi:** Buat Process Group khusus untuk `Virtualization Ingestion`.
3. **Implementasi API Polling:**
   - Gunakan processor `InvokeHTTP` diarahkan ke Mock API lokal.
   - Konfigurasi parameter autentikasi (menggunakan kredensial dari HashiCorp Vault sebagai simulasi).
4. **Data Normalization:**
   - Tambahkan processor `JoltTransformJSON` dengan spesifikasi `vm-normalize.jolt`.
5. **Validation & Kafka Publishing:**
   - Tambahkan processor `ValidateRecord` dan konfigurasikan Avro schema `event-schema.avsc`.
   - Publish ke topic `dcim.events.raw`.

---

## 2. ST-392: Konektor ITSM (ServiceNow & Jira Integration)
**Terkait MT-014 (Data Ingestion Pipelines)**  
**Status:** Waiting

### Deskripsi:
Implementasi konektor REST API bidirectional untuk ServiceNow dan Jira menggunakan **Mock API / Fixture** untuk readiness.

### Rincian Pengerjaan:
1. **Pembuatan Mock API (Fixture):** Buat Mock server untuk merespon request pembuatan tiket Jira/ServiceNow.
2. **ServiceNow & Jira Integration Script:**
   - Implementasi `ServiceNowConnector` dan `JiraConnector`.
   - Event mappings untuk create Incident / Issue.
3. **Konfigurasi Autentikasi:** Simulasi penarikan token OAuth2/API Key dari HashiCorp Vault.

---

## 3. ST-393: S3/MinIO Cold Storage Archiving Pipeline
**Terkait MT-014 (Data Ingestion Pipelines)**  
**Status:** On-Hold (Ditunda)

### Deskripsi:
**DITUNDA**: Kebutuhan ini ditunda terlebih dahulu mengingat arsitektur perusahaan saat ini belum membutuhkan dan belum memiliki infrastruktur cloud services (AWS S3) maupun kebutuhan mendesak untuk MinIO Cold Storage.

---

## 4. ST-394: End-to-End Integration Testing & Performance Load Test
**Terkait MT-040 (Integration Testing)**  
**Status:** Waiting

### Deskripsi:
Pengujian end-to-end pipeline untuk memverifikasi kesehatan data pipeline dari hulu (termasuk mock api) hingga hilir (Elasticsearch / DB).

### Rincian Pengerjaan:
1. **Load Generation & Stress Testing:** Sustain traffic metrics untuk tes stabilitas.
2. **Verifikasi Latency (p99 < 1s):** Pastikan processing delay di NiFi dan Normalization script aman.
3. **Verifikasi Quality Gates:** Validasi bahwa payload yang cacat masuk ke DLQ tanpa merusak pipeline utama.

