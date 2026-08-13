# Implementation Plan — Remaining Gaps v4.7.0 Pipeline Architecture

**Author:** Imam Syauqi Achmad  
**Date:** 2026-08-13  
**Host:** srv-rnd-dcim (10.70.0.56)  

Berdasarkan komparasi v4.7.0 dan dokumen referensi Block 2 DCIM-Wiki, berikut adalah rencana implementasi untuk gap yang tersisa:

## Fase 1: S3/MinIO Cold Storage Archiving (ST-393)

### 1.1 Persiapan Storage
- Setup MinIO local bucket / gunakan AWS S3 mock
- Tambahkan credential MinIO/S3 ke HashiCorp Vault.

### 1.2 NiFi DLQ Archiving
- Tambahkan Processor `PutS3Object` di akhir rute DLQ (`delivery-failure`, `enrichment-failure`, `parse-failure`).
- Konfigurasi bucket target (`dcim-dlq-archive`).

### 1.3 Telemetry Long-term Retention
- Bikin consumer group Kafka `dcim_s3_archive_consumer` yang subscribe ke `dcim.events.raw` dan `dcim.enriched.events`.
- Tulis batch object ke S3 bucket `dcim-telemetry-archive`.

## Fase 2: Virtualization/Cloud Collector (ST-391)

### 2.1 VMware vSphere / Proxmox NiFi Flow
- Bikin NiFi Process Group `Virtualization Ingestion`.
- Pakai `InvokeHTTP` untuk get metrics dari Proxmox VE API / vCenter REST API.
- Processor: `InvokeHTTP` -> `JoltTransformJSON` (vm-normalize.jolt) -> `ValidateRecord` -> `PublishKafka_2_0` (Topic: `dcim.events.raw`).

## Fase 3: Konektor ITSM (ServiceNow & Jira) (ST-392)

### 3.1 ServiceNow Integration
- Buat `ServiceNowConnector` (REST API + OAuth2).
- Event mappings untuk create Incident.
- Bidirectional state sync (Incident closed di ServiceNow -> Update event state di DCIM).

### 3.2 Jira Integration
- Buat `JiraConnector` (REST API + API Key).
- Event mappings untuk create Issue.

## Fase 4: End-to-End Integration & Load Testing (ST-394)

### 4.1 Load Generation
- Generate synthetic metrics/events payload to sustain 430 eps load.

### 4.2 Verifikasi Acceptance Criteria Block 2
- Test schema validator with invalid payload.
- Validasi lineage dan pipeline observability metrics (Prometheus).
- Verifikasi p99 latency < 1s via Grafana.
