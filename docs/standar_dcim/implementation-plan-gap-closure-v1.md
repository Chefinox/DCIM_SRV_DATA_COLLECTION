# Implementation Plan — Gap Closure `dcim_metrics_project` terhadap Spesifikasi `dcim-core-platform`

**Author:** Imam Syauqi Achmad  
**Date:** 2026-08-10  
**Host:** srv-rnd-dcim (10.70.0.56)  
**Repo:** `Chefinox/DCIM_SRV_DATA_COLLECTION`

---

## Status Baseline Gap (Verifikasi Ulang 2026-08-10)

Semua gap diverifikasi langsung terhadap kode aktual — **grep kosong = belum ada**.

| # | Komponen | Skor | Gap yang Terkonfirmasi Masih Ada | Prioritas |
|---|---|---|---|---|
| 1 | Validation & Normalizer | **55%** | Tidak ada range/format/dedup/freshness/source-allowlist validation | **P1 CRITICAL** |
| 2 | Disposition & Deduplication | **0%** | Tidak ada ClaimStore/content-hash dedup protocol | **P1** |
| 3 | Prometheus Pipeline Metrics | **0%** | Tidak ada `dii_*` pipeline metrics (hanya 2 circuit breaker gauge) | **P1** |
| 4 | Concurrency Control (Pollers) | **0%** | Tidak ada rate limiter/semaphore pada telemetry pollers | **P2** |
| 5 | Kill Switch (Pollers) | **0%** | Tidak ada config-flag/stop-file per-poller, hanya systemd/NiFi stop | **P2** |
| 6 | Impact Scoring | **0%** | Tidak ada `criticality × severity` calculation | **P2** |
| 7 | Data Quality Scorecard | **0%** | Tidak ada 6-dimensi quality score ke Prometheus | **P2** |
| 8 | Workflow Engine | **0%** | Tidak ada workflow/approval/draft-ticket module | **P3** |

---

## Urutan Implementasi

### Fase 1: Core Validation Pipeline (P1 — wajib duluan)

#### 1A. Validation Processor Engine

**Tujuan:** Tambahkan modul validasi event di normalizer pipeline yang mengevaluasi setiap normalized event sebelum diteruskan ke enrichment.

**Lokasi:** `src/validation/` (modul baru)

**File yang Dibuat:**

| File | Deskripsi |
|------|-----------|
| `src/validation/__init__.py` | Package init |
| `src/validation/engine.py` | `ValidationEngine` — orchestrator yang menjalankan chain of rules |
| `src/validation/rules.py` | Rule implementations: `RangeRule`, `FormatRule`, `FreshnessRule`, `SourceAllowlistRule` |
| `src/validation/config.py` | Config loader — baca aturan validasi dari YAML |
| `configs/validation_rules.yaml` | Konfigurasi aturan validasi per metric type |
| `tests/test_validation_engine.py` | Unit test komprehensif |

**Arsitektur:**

```
NormalizedEvent (dari normalizer)
    │
    ▼
┌─────────────────────────────┐
│     ValidationEngine        │
│  ┌───────────────────────┐  │
│  │ 1. RangeRule           │  │  metric_value within min/max per metric_name
│  │ 2. FormatRule          │  │  regex validation (IP: RFC 5737, MAC, UUID)
│  │ 3. FreshnessRule       │  │  event_time within max staleness window
│  │ 4. SourceAllowlistRule │  │  source_topic in registered allowlist
│  └───────────────────────┘  │
│                             │
│  Result: ValidationResult   │
│  - status: accepted/quarantined
│  - failed_rules: [reason]   │
│  - quality_flags: [warning] │
└──────────┬──────────────────┘
           │
     ┌─────┴─────┐
     │           │
  accepted    quarantined
     │           │
     ▼           ▼
  Enrichment   DLQ (dcim.dlq.parse-failure)
```

**Aturan Validasi (configs/validation_rules.yaml):**

```yaml
rules:
  range:
    enabled: true
    metrics:
      cpu_usage_percent:
        min: 0
        max: 100
      temperature_celsius:
        min: -40
        max: 150
      memory_usage_percent:
        min: 0
        max: 100
      disk_usage_percent:
        min: 0
        max: 100
      input_voltage:
        min: 0
        max: 500
      output_load_percent:
        min: 0
        max: 100
      battery_capacity_percent:
        min: 0
        max: 100

  format:
    enabled: true
    fields:
      ip_address:
        pattern: "^(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)$"
      mac_address:
        pattern: "^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$"
      uuid:
        pattern: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

  freshness:
    enabled: true
    max_staleness_seconds: 300  # 5 menit

  source_allowlist:
    enabled: true
    allowed_topics:
      - "dcim.raw.hardware.server"
      - "dcim.raw.network.switch"
      - "dcim.raw.power.ups"
      - "dcim.raw.storage.nas"
      - "dcim.raw.cctv"
      - "dcim.raw.device.isapi"
```

**Integrasi ke Normalizer:**

```
Perubahan di: src/skills/telemetry/normalizer/executor.py
- Setelah normalisasi (sebelum Avro serialization)
- Import ValidationEngine
- Panggil engine.validate(normalized_event)
- Jika quarantined → kirim ke DLQ topic, catat di lineage
- Jika accepted → lanjut ke enriched topic
```

---

#### 1B. Deduplication Engine

**Tujuan:** Deteksi dan filter event duplikat berdasarkan content hash dalam sliding window.

**Lokasi:** `src/validation/dedup.py` (bagian dari modul validation)

**File yang Dibuat:**

| File | Deskripsi |
|------|-----------|
| `src/validation/dedup.py` | `DeduplicationChecker` — Redis-backed sliding window dedup |

**Mekanisme:**
- Hash: SHA-256 dari `f"{event_id}:{metric_name}:{metric_value}:{hostname}:{serial_number}"`
- Window: Configurable TTL di Redis (default 60 detik)
- Lookup: `SETNX` pada key `dedup:{hash}` dengan TTL
- Jika key sudah ada → `duplicate`, kirim ke DLQ
- Jika key baru → `accepted`, lanjut pipeline

---

#### 1C. Prometheus Pipeline Metrics

**Tujuan:** Tambahkan `prometheus_client` metrics untuk observabilitas pipeline.

**Lokasi:** `src/observability/metrics.py` (modul baru)

**File yang Dibuat/Diubah:**

| File | Deskripsi |
|------|-----------|
| `src/observability/metrics.py` | Pipeline metric definitions |
| `src/observability/metrics_server.py` | HTTP server yang expose `/metrics` |
| `configs/systemd/dcim-metrics-server.service` | Systemd unit |

**Metrics:**

```python
# Counter
dii_events_ingested_total    = Counter('dii_events_ingested_total', 'Events ingested', ['source_topic'])
dii_events_validated_total   = Counter('dii_events_validated_total', 'Events validated', ['status'])  # accepted/quarantined/duplicate
dii_events_enriched_total    = Counter('dii_events_enriched_total', 'Events enriched', ['status'])
dii_events_routed_total      = Counter('dii_events_routed_total', 'Events routed', ['target_store'])
dii_validation_rejected_total = Counter('dii_validation_rejected_total', 'Rejected events', ['reason'])

# Histogram
dii_validation_latency_seconds   = Histogram('dii_validation_latency_seconds', 'Validation latency')
dii_enrichment_latency_seconds   = Histogram('dii_enrichment_latency_seconds', 'Enrichment latency')
dii_e2e_processing_seconds       = Histogram('dii_e2e_processing_seconds', 'End-to-end latency')

# Gauge
dii_dlq_messages_total = Gauge('dii_dlq_messages_total', 'DLQ unprocessed', ['topic'])
```

**Integrasi:** Instrument normalizer, enrichment API, ES consumer, DLQ consumer.

---

### Fase 2: Connector Hardening (P2)

#### 2A. Poller Concurrency Control & Rate Limiter

**Tujuan:** Tambahkan bounded concurrency dan rate limiting ke telemetry pollers.

**Lokasi:** `src/utils/rate_limiter.py` (modul baru)

**File yang Dibuat/Diubah:**

| File | Deskripsi |
|------|-----------|
| `src/utils/rate_limiter.py` | `PollRateLimiter` class — sliding window rate limit + semaphore |
| `scripts/redfish_poller.py` | Integrasi rate limiter |
| `scripts/mikrotik_poller.py` | Integrasi rate limiter |
| `scripts/snmp_ups_poller.py` | Integrasi rate limiter |
| `scripts/nas_poller.py` | Integrasi rate limiter |

**Parameter per source class:**

| Source Class | Max Concurrent | Max Req/Min | Backoff |
|---|---|---|---|
| Redfish BMC | 2 | 10 | Decorrelated jitter |
| SNMP (Mikrotik/UPS) | 1 | 10 | Decorrelated jitter |
| NAS REST | 2 | 15 | Decorrelated jitter |
| CCTV/ISAPI | 1 | 5 | Decorrelated jitter |

---

#### 2B. Poller Kill Switch (3-tier)

**Tujuan:** Tambahkan mekanisme kill switch yang bisa menghentikan poller tanpa restart service.

**Lokasi:** `src/utils/kill_switch.py` (modul baru)

**Mekanisme:**

1. **Tier 1 — Config flag:** Baca `configs/poller_config.yaml` → field `enabled: true/false` per poller, hot-reloadable setiap cycle.
2. **Tier 2 — Stop file:** Cek keberadaan `/tmp/dcim_stop_{poller_name}` sebelum setiap poll cycle.
3. **Tier 3 — SIGTERM:** Graceful shutdown handler (sudah ada via systemd, perlu cleanup handler).

---

### Fase 3: Enrichment Enhancement (P2)

#### 3A. Impact Scoring Engine

**Tujuan:** Kalkulasi impact score = `criticality_weight × severity_weight`.

**Lokasi:** `src/scoring/impact.py` (modul baru)

**File yang Dibuat:**

| File | Deskripsi |
|------|-----------|
| `src/scoring/__init__.py` | Package init |
| `src/scoring/impact.py` | `ImpactScorer` — rule-based scoring engine |
| `configs/impact_scoring.yaml` | Weight matrix config |

**Weight Matrix:**

```yaml
criticality_weights:
  critical: 5
  high: 4
  medium: 3
  low: 2
  minimal: 1

severity_weights:
  critical: 5
  warning: 3
  info: 1

impact_thresholds:
  P1: 15    # criticality × severity >= 15
  P2: 6     # >= 6
  P3: 1     # < 6
```

**Integrasi:** Enrichment API menambahkan `impact_score` dan `impact_priority` ke response.

---

#### 3B. Data Quality Scorecard (6-Dimensi)

**Tujuan:** Kalkulasi dan export 6-dimensi data quality score ke Prometheus.

**Lokasi:** `src/scoring/data_quality.py` (modul baru)

**6 Dimensi:**

| Dimensi | Definisi | Pengukuran |
|---------|---------|------------|
| **Completeness** | % event dengan semua mandatory fields terisi | `filled_fields / total_mandatory_fields` |
| **Timeliness** | % event yang arrive dalam freshness window | `fresh_events / total_events` |
| **Accuracy** | % event yang lolos range validation | `in_range_events / total_events` |
| **Consistency** | % event dengan format fields valid | `valid_format_events / total_events` |
| **Validity** | % event yang lolos schema validation | `schema_valid_events / total_events` |
| **Uniqueness** | % event yang bukan duplicate | `unique_events / total_events` |

**Export:** Prometheus gauges per-dimensi, di-update setiap 60 detik.

---

### Fase 4: Dokumentasi & Referensi (P3)

#### 4A. Workflow Engine Stub

**Catatan:** Workflow engine (Temporal/n8n) belum prioritas untuk implementasi di host ini. Akan didokumentasikan sebagai desain target saja, bukan implementasi aktual.

---

## Ringkasan File Changes

### File Baru (16 file)

| # | Path | Fase |
|---|------|------|
| 1 | `src/validation/__init__.py` | 1A |
| 2 | `src/validation/engine.py` | 1A |
| 3 | `src/validation/rules.py` | 1A |
| 4 | `src/validation/config.py` | 1A |
| 5 | `src/validation/dedup.py` | 1B |
| 6 | `configs/validation_rules.yaml` | 1A |
| 7 | `src/observability/metrics.py` | 1C |
| 8 | `src/observability/metrics_server.py` | 1C |
| 9 | `configs/systemd/dcim-metrics-server.service` | 1C |
| 10 | `src/utils/rate_limiter.py` | 2A |
| 11 | `src/utils/kill_switch.py` | 2B |
| 12 | `configs/poller_config.yaml` | 2B |
| 13 | `src/scoring/__init__.py` | 3A |
| 14 | `src/scoring/impact.py` | 3A |
| 15 | `src/scoring/data_quality.py` | 3B |
| 16 | `configs/impact_scoring.yaml` | 3A |

### File Diubah (8 file)

| # | Path | Perubahan | Fase |
|---|------|-----------|------|
| 1 | `src/skills/telemetry/normalizer/executor.py` | Integrasi ValidationEngine | 1A |
| 2 | `scripts/redfish_poller.py` | Rate limiter + kill switch | 2A/2B |
| 3 | `scripts/mikrotik_poller.py` | Rate limiter + kill switch | 2A/2B |
| 4 | `scripts/snmp_ups_poller.py` | Rate limiter + kill switch | 2A/2B |
| 5 | `scripts/nas_poller.py` | Rate limiter + kill switch | 2A/2B |
| 6 | `scripts/hikvision_poller_daemon.py` | Kill switch | 2B |
| 7 | `scripts/cctv_poller.py` | Rate limiter + kill switch | 2A/2B |
| 8 | `src/skills/inventory/enrichment/executor.py` | Impact score field | 3A |

### Unit Test Baru (4 file)

| # | Path | Cakupan |
|---|------|---------|
| 1 | `tests/test_validation_engine.py` | Validation engine + rules |
| 2 | `tests/test_dedup.py` | Deduplication checker |
| 3 | `tests/test_impact_scoring.py` | Impact scoring engine |
| 4 | `tests/test_data_quality.py` | Data quality scorecard |

---

## Urutan Commit (di `dcim_metrics_project`)

| # | Commit Message | Fase | Dependensi |
|---|---|---|---|
| 1 | `feat(validation): add validation engine with range, format, freshness, source-allowlist rules` | 1A | — |
| 2 | `feat(validation): add Redis-backed deduplication checker with sliding window` | 1B | 1A |
| 3 | `feat(validation): integrate validation engine into normalizer pipeline` | 1A | 1A, 1B |
| 4 | `feat(observability): add prometheus_client pipeline metrics and HTTP server` | 1C | — |
| 5 | `feat(connectors): add rate limiter and concurrency control to telemetry pollers` | 2A | — |
| 6 | `feat(connectors): add 3-tier kill switch to all pollers` | 2B | — |
| 7 | `feat(scoring): add impact scoring engine with criticality × severity matrix` | 3A | — |
| 8 | `feat(scoring): add 6-dimension data quality scorecard with Prometheus export` | 3B | 1A |

---

## Dependensi Python Baru

```
prometheus_client>=0.20.0   # sudah tersedia jika netbox sync pernah diinstall
pyyaml>=6.0                 # untuk config YAML
```

Redis (`redis-py`) sudah terinstall di host (dipakai oleh enrichment API).

---

## Estimasi Dampak pada Service yang Berjalan

| Service | Dampak | Tindakan |
|---------|--------|----------|
| `dcim-normalizer.service` | **Perlu restart** setelah integrasi validation engine | Restart setelah commit 3 |
| `dcim-enrichment-api.service` | **Perlu restart** setelah integrasi impact scoring | Restart setelah commit 7 |
| Semua poller services | **Perlu restart** setelah integrasi rate limiter & kill switch | Restart setelah commit 5 & 6 |
| `dcim-metrics-server.service` | **Service baru** | Enable & start setelah commit 4 |
| Prometheus (10.70.0.25) | Perlu tambah scrape target baru | Update `prometheus.yml` |

---

## Risiko & Mitigasi

| Risiko | Mitigasi |
|--------|---------|
| Validation engine menolak terlalu banyak event (false positive) | Mulai dengan `dry_run: true` mode — log saja, jangan reject. Evaluasi 24 jam sebelum enforce. |
| Rate limiter memperlambat polling | Set limit konservatif (sesuai ADR-0023), monitor via Prometheus |
| Redis dedup key exhaustion | Set TTL pendek (60s default), monitor Redis memory |
| Restart service mengganggu pipeline | Restart satu per satu, monitor DLQ untuk spike |

---

Menunggu persetujuan untuk mulai eksekusi **Fase 1A (Validation Engine)**.
