---
title: "Block 2 — Data Ingestion & Integration: Reference Design Spec"
created: 2026-06-23
updated: 2026-06-23
type: reference-design
block: 2
phase: 1
status: generated
confidence: high
tags: [data-ingestion, kafka, nifi, validation, enrichment, dlq, lineage, itsm, erp]
wiki_pages:
  - data-ingestion-integration
  - kafka
  - nifi
  - data-quality-runbook
  - dcim-data-flow-architecture
  - cmdb
  - asset-repository
purpose: >
  Reference design spec untuk Block 2 Data Ingestion & Integration.
  Tim gunakan untuk komparasi dengan implementasi aktual.
  Gap = connection dots.
---

# Block 2 — Data Ingestion & Integration: Reference Design Spec

> **Purpose:** Dokumen referensi lengkap untuk DI&I gateway — single entry point semua data ke DCIM platform.
> **Cara pakai:** Tim komparasi side-by-side dengan implementasi aktual. Setiap gap dicatat sebagai connection point.
> **Architecture Diagram:** `diagrams/block2-data-ingestion-architecture.html` — buka di browser untuk visualisasi interaktif.
> **Depends on:** Block 1 (Infrastructure Provisioning)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Normalized Event Schema](#2-normalized-event-schema)
3. [Kafka Topic Architecture](#3-kafka-topic-architecture)
4. [NiFi Flow Designs](#4-nifi-flow-designs)
5. [Validation Processor](#5-validation-processor)
6. [Enrichment Processor](#6-enrichment-processor)
7. [DLQ Handling](#7-dlq-handling)
8. [Data Lineage Tracking](#8-data-lineage-tracking)
9. [ITSM/ERP/DMS Connectors](#9-itsmerpdms-connectors)
10. [Data Quality Framework](#10-data-quality-framework)
11. [Error Handling Strategy](#11-error-handling-strategy)
12. [Performance & Sizing](#12-performance--sizing)
13. [Security](#13-security)
14. [Monitoring & Alerting](#14-monitoring--alerting)
15. [Acceptance Criteria](#15-acceptance-criteria)
16. [NVR Connector Flows](#17-nvr-connector-flows)
17. [Gap Comparison Template](#18-gap-comparison-template)

---

## 1. Architecture Overview

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DI&I Gateway (Data Ingestion & Integration)      │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ NiFi     │  │ NiFi     │  │ NiFi     │  │ NiFi     │          │
│  │ BMS/EPMS │  │ NMS      │  │ Server   │  │ Cloud/   │          │
│  │ Flow     │  │ Flow     │  │ Storage  │  │ VM       │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │              │                │
│  ┌────┴──────────────┴──────────────┴──────────────┴─────┐         │
│  │              Kafka: dcim.events.raw                    │         │
│  └────────────────────────┬───────────────────────────────┘         │
│                           │                                         │
│  ┌────────────────────────┴───────────────────────────────┐         │
│  │         Validation Processor (Schema + Type + Range)   │         │
│  └────────────────────────┬───────────────────────────────┘         │
│                           │                                         │
│              ┌────────────┴────────────┐                           │
│              │                         │                           │
│              ▼                         ▼                           │
│  ┌───────────────────┐    ┌────────────────────┐                   │
│  │ Kafka:            │    │ Kafka:             │                   │
│  │ dcim.events       │    │ dcim.events.dlq    │                   │
│  │ .validated        │    │ (Dead Letter)      │                   │
│  └────────┬──────────┘    └────────────────────┘                   │
│           │                                                         │
│  ┌────────┴──────────────────────────────┐                         │
│  │    Enrichment Processor               │                         │
│  │    (CI lookup, Location, Priority)    │                         │
│  └────────┬──────────────────────────────┘                         │
│           │                                                         │
│  ┌────────┴──────────┐                                            │
│  │ Kafka:            │                                            │
│  │ dcim.events       │                                            │
│  │ .enriched         │                                            │
│  └────────┬──────────┘                                            │
│           │                                                         │
│  ┌────────┴──────────────────────────────┐                         │
│  │         Router                        │                         │
│  │  (Route by event_type → target store) │                         │
│  └───┬────────┬────────┬────────┬────────┘                         │
│      │        │        │        │                                   │
│      ▼        ▼        ▼        ▼                                   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  │ CMDB │ │Asset │ │Time  │ │ SIEM │                              │
│  │      │ │ Repo │ │Series│ │      │                              │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow Summary

```
Source Systems → NiFi (ingest) → Kafka raw → Validation → Kafka validated/enriched
                                ↓ (fail)
                              Kafka DLQ → Retry → DLQ

Kafka enriched → Router → CMDB / Asset / Time-Series / SIEM

Cross-cutting: Lineage Tracker (logs every step)
```

### 1.3 Processing Modes

| Mode | Latency | Use Case | Components |
|------|---------|----------|------------|
| Real-time | < 1s | Critical alerts (P1), security events | Kafka → Flink/Stream processor |
| Near-real-time | 1-30s | Operational metrics, status changes | Kafka → Consumer |
| Batch | 1-60 min | Historical sync, bulk import | NiFi scheduled → Kafka |
| Async | > 1h | Report generation, reconciliation | Background jobs |

---

## 2. Normalized Event Schema

### 2.1 Base Event Schema (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://dcim.local/schemas/event-v1.json",
  "title": "DCIM Event",
  "description": "Unified event schema for all DCIM platform events",
  "type": "object",
  "required": ["event_id", "timestamp", "source_system", "event_type", "payload"],
  "properties": {
    "event_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique event identifier (UUID v4)"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Event timestamp (ISO 8601)"
    },
    "source_system": {
      "type": "string",
      "enum": [
        "bms", "epms", "ems",
        "nms",
        "server_monitor", "storage_monitor",
        "vmware", "aws", "gcp", "azure",
        "access_control", "surveillance",
        "itsm", "erp", "dms",
        "manual", "api"
      ],
      "description": "Source system identifier"
    },
    "event_type": {
      "type": "string",
      "pattern": "^[a-z]+\\.[a-z]+\\.[a-z_]+$",
      "description": "Event type (namespace.category.action)"
    },
    "payload": {
      "type": "object",
      "description": "Event-specific payload data"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "priority": {
          "type": "string",
          "enum": ["P1", "P2", "P3", "P4"],
          "default": "P3"
        },
        "category": {
          "type": "string",
          "enum": [
            "power", "cooling", "environment",
            "network", "compute", "storage",
            "security", "access", "compliance",
            "capacity", "performance", "availability"
          ]
        },
        "tags": {
          "type": "array",
          "items": { "type": "string" },
          "maxItems": 10
        },
        "correlation_id": {
          "type": "string",
          "format": "uuid",
          "description": "Cross-event correlation ID"
        },
        "causation_id": {
          "type": "string",
          "format": "uuid",
          "description": "ID of event that caused this event"
        },
        "schema_version": {
          "type": "string",
          "default": "1.0.0"
        }
      },
      "required": ["priority", "category"]
    },
    "enrichment": {
      "type": "object",
      "description": "Added by enrichment processor",
      "properties": {
        "ci_id": {
          "type": "string",
          "description": "Related CI ID from CMDB"
        },
        "asset_id": {
          "type": "string",
          "description": "Related Asset ID from Asset Repository"
        },
        "location": {
          "type": "object",
          "properties": {
            "site": { "type": "string" },
            "building": { "type": "string" },
            "floor": { "type": "string" },
            "room": { "type": "string" },
            "rack": { "type": "string" },
            "u_position": { "type": "string" }
          }
        },
        "impact_score": {
          "type": "number",
          "minimum": 0,
          "maximum": 10
        },
        "enriched_at": {
          "type": "string",
          "format": "date-time"
        }
      }
    }
  }
}
```

### 2.2 Event Type Taxonomy

| Namespace | Category | Actions | Example |
|-----------|----------|---------|---------|
| `power` | `epms` | `status_change`, `alarm`, `metrics` | `power.epms.alarm` |
| `cooling` | `bms` | `status_change`, `alarm`, `metrics` | `cooling.bms.alarm` |
| `environment` | `bms` | `temperature`, `humidity`, `alarm` | `environment.bms.temperature` |
| `network` | `nms` | `up_down`, `metrics`, `config_change` | `network.nms.up_down` |
| `compute` | `server` | `status_change`, `metrics`, `alarm` | `compute.server.metrics` |
| `storage` | `san` | `capacity`, `performance`, `alarm` | `storage.san.capacity` |
| `virtualization` | `vmware` | `vm_lifecycle`, `resource_change` | `virtualization.vmware.vm_lifecycle` |
| `security` | `access` | `door_event`, `alarm`, `analytics` | `security.access.door_event` |
| `security` | `surveillance` | `motion_detect`, `line_cross` | `security.surveillance.motion_detect` |

### 2.3 Event Examples

#### Power Alarm Event

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-06-23T14:30:00.000Z",
  "source_system": "epms",
  "event_type": "power.epms.alarm",
  "payload": {
    "device_id": "ups-rack-a1-01",
    "alarm_name": "input_voltage_low",
    "severity": "critical",
    "value": 185.2,
    "unit": "V",
    "threshold": 200.0,
    "state": "active"
  },
  "metadata": {
    "priority": "P1",
    "category": "power",
    "tags": ["ups", "rack-a1", "critical"],
    "correlation_id": "660e8400-e29b-41d4-a716-446655440000",
    "schema_version": "1.0.0"
  }
}
```

#### Network Up/Down Event

```json
{
  "event_id": "770e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2026-06-23T14:31:00.000Z",
  "source_system": "nms",
  "event_type": "network.nms.up_down",
  "payload": {
    "device_id": "switch-floor3-01",
    "interface": "GigabitEthernet0/1",
    "status": "down",
    "previous_status": "up",
    "uptime_seconds": 864000,
    "vendor": "cisco",
    "model": "C9300"
  },
  "metadata": {
    "priority": "P2",
    "category": "network",
    "tags": ["switch", "floor3", "interface-down"],
    "schema_version": "1.0.0"
  }
}
```

### 2.4 Schema Versioning Strategy

| Version Change | When | Impact |
|---------------|------|--------|
| Patch (1.0.x) | Add optional field | Backward compatible |
| Minor (1.x.0) | Add new enum value, new optional section | Backward compatible |
| Major (x.0.0) | Remove/rename field, change type | Breaking — new topic version |

```yaml
# Schema registry config
schema_registry:
  url: http://schema-registry:8081
  compatibility: BACKWARD
  compatibility_level: BACKWARD
```

---

## 3. Kafka Topic Architecture

### 3.1 Topic Map

| Topic | Partitions | RF | Retention | Cleanup | Throughput | Consumer |
|-------|------------|-----|-----------|---------|------------|----------|
| `dcim.events.raw` | 12 | 3 | 7 days | delete | High (430 eps) | Validation |
| `dcim.events.validated` | 12 | 3 | 30 days | delete | High | Enrichment |
| `dcim.events.enriched` | 12 | 3 | 90 days | delete | High | Router |
| `dcim.events.dlq` | 6 | 3 | 30 days | compact | Low | DLQ Monitor |
| `dcim.cmdb.updates` | 6 | 3 | 90 days | compact | Medium | CMDB Consumer |
| `dcim.asset.updates` | 6 | 3 | 90 days | compact | Medium | Asset Consumer |
| `dcim.siem.events` | 12 | 3 | 90 days | delete | Medium | SIEM Consumer |
| `dcim.analytics.metrics` | 6 | 3 | 7 days | delete | High | Analytics Engine |
| `dcim.workflow.events` | 6 | 3 | 30 days | delete | Low | Workflow Engine |
| `dcim.lineage.events` | 3 | 3 | 7 days | delete | Low | Lineage Store |

### 3.2 Partition Key Strategy

| Topic | Partition Key | Reasoning |
|-------|--------------|-----------|
| `dcim.events.raw` | `source_system` | Ensure ordering per source |
| `dcim.events.validated` | `event_id` | Even distribution |
| `dcim.events.enriched` | `event_id` | Even distribution |
| `dcim.events.dlq` | `source_system` | Group by source for retry |
| `dcim.cmdb.updates` | `ci_id` | Ensure ordering per CI |
| `dcim.asset.updates` | `asset_id` | Ensure ordering per asset |

### 3.3 Topic Configuration Details

```json
{
  "cleanup.policy": "delete",
  "retention.ms": 604800000,
  "min.insync.replicas": 2,
  "replication.factor": 3,
  "compression.type": "lz4",
  "max.message.bytes": 1048576,
  "segment.bytes": 1073741824,
  "segment.ms": 604800000,
  "flush.messages": 10000,
  "flush.ms": 1000
}
```

### 3.4 Consumer Group Design

| Consumer Group | Topics | Parallelism | Offset Policy |
|---------------|--------|-------------|---------------|
| `dii-validation` | `dcim.events.raw` | 12 (1 per partition) | auto-commit |
| `dii-enrichment` | `dcim.events.validated` | 12 | manual-commit |
| `dii-routing` | `dcim.events.enriched` | 12 | manual-commit |
| `dii-dlq-monitor` | `dcim.events.dlq` | 3 | manual-commit |
| `cmdb-consumer` | `dcim.cmdb.updates` | 6 | manual-commit |
| `asset-consumer` | `dcim.asset.updates` | 6 | manual-commit |
| `siem-consumer` | `dcim.siem.events` | 6 | manual-commit |
| `analytics-consumer` | `dcim.analytics.metrics` | 6 | manual-commit |
| `lineage-consumer` | `dcim.lineage.events` | 3 | manual-commit |

---

## 4. NiFi Flow Designs

### 4.1 Common Flow Pattern

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Ingest   │──→│ Validate │──→│ Normalize│──→│ Enrich   │──→│ Publish  │
│ Processor│   │ Processor│   │ Processor│   │ Processor│   │ Kafka    │
└──────────┘   └────┬─────┘   └──────────┘   └──────────┘   └──────────┘
                    │ fail
                    ▼
              ┌──────────┐
              │ DLQ      │
              │ Route    │
              └──────────┘
```

### 4.2 BMS/EPMS Flow

| Processor | Class | Config |
|-----------|-------|--------|
| **GetHTTP** | `o.a.n.p.standard.GetHTTP` | URL: `${bms.api.url}`, Polling: 30s |
| **JoltTransformJSON** | `o.a.n.p.standard.JoltTransformJSON` | Spec: `bms-normalize.jolt` |
| **ValidateRecord** | `o.a.n.p.standard.ValidateRecord` | Schema: `event-schema.avsc`, Reject: DLQ |
| **PublishKafka_2_0** | `o.a.n.p.kafka.PublishKafka_2_0` | Topic: `dcim.events.raw`, Key: `${source_system}` |
| **PutS3Object** | `o.a.n.p.aws.s3.PutS3Object` | Bucket: `${dlq.bucket}`, Prefix: `bms/` |

#### Jolt Spec (BMS Normalize)

```json
[
  {
    "operation": "shift",
    "spec": {
      "device_id": "device_id",
      "timestamp": "timestamp",
      "readings": {
        "*": {
          "name": "payload.readings[&1].name",
          "value": "payload.readings[&1].value",
          "unit": "payload.readings[&1].unit"
        }
      },
      "alarms": {
        "*": {
          "name": "payload.alarms[&1].name",
          "severity": "payload.alarms[&1].severity",
          "state": "payload.alarms[&1].state"
        }
      }
    }
  },
  {
    "operation": "default",
    "spec": {
      "source_system": "bms",
      "event_type": "cooling.bms.metrics",
      "metadata": {
        "priority": "P3",
        "category": "cooling",
        "schema_version": "1.0.0"
      }
    }
  },
  {
    "operation": "java.math.BigDecimal",
    "spec": {
      "payload.readings[*].value": "toNumber"
    }
  }
]
```

### 4.3 NMS Flow

| Processor | Class | Config |
|-----------|-------|--------|
| **GetSNMP** | `o.a.n.p.snmp.GetSNMP` | SNMPv3, Target: `${nms.host}`, OID: interface table |
| **SplitRecord** | `o.a.n.p.standard.SplitRecord` | Record Reader: JSON, Writer: JSON |
| **JoltTransformJSON** | `o.a.n.p.standard.JoltTransformJSON` | Spec: `nms-normalize.jolt` |
| **ValidateRecord** | `o.a.n.p.standard.ValidateRecord` | Schema: `event-schema.avsc` |
| **PublishKafka_2_0** | `o.a.n.p.kafka.PublishKafka_2_0` | Topic: `dcim.events.raw` |

### 4.4 Server/Storage Flow

| Processor | Class | Config |
|-----------|-------|--------|
| **ExecuteStreamCommand** | `o.a.n.p.standard.ExecuteStreamCommand` | Command: SSH script for metrics collection |
| **SplitText** | `o.a.n.p.standard.SplitText` | Line delimiter |
| **ConvertRecord** | `o.a.n.p.standard.ConvertRecord` | Reader: CSV, Writer: JSON |
| **JoltTransformJSON** | `o.a.n.p.standard.JoltTransformJSON` | Spec: `server-normalize.jolt` |
| **PublishKafka_2_0** | `o.a.n.p.kafka.PublishKafka_2_0` | Topic: `dcim.events.raw` |

### 4.5 Virtualization/Cloud Flow

| Processor | Class | Config |
|-----------|-------|--------|
| **InvokeHTTP** | `o.a.n.p.standard.InvokeHTTP` | VMware vSphere API / AWS SDK |
| **JoltTransformJSON** | `o.a.n.p.standard.JoltTransformJSON` | Spec: `vm-normalize.jolt` |
| **ValidateRecord** | `o.a.n.p.standard.ValidateRecord` | Schema: `event-schema.avsc` |
| **PublishKafka_2_0** | `o.a.n.p.kafka.PublishKafka_2_0` | Topic: `dcim.events.raw` |

### 4.6 Access Control/Surveillance Flow

| Processor | Class | Config |
|-----------|-------|--------|
| **GetFile** | `o.a.n.p.standard.GetFile` | Directory: `${badge.drop.path}`, Batch: 100 |
| **ConvertRecord** | `o.a.n.p.standard.ConvertRecord` | Reader: CSV, Writer: JSON |
| **JoltTransformJSON** | `o.a.n.p.standard.JoltTransformJSON` | Spec: `access-normalize.jolt` |
| **PublishKafka_2_0** | `o.a.n.p.kafka.PublishKafka_2_0` | Topic: `dcim.events.raw` |

### 4.7 NiFi Error Handling Matrix

| Error Type | Route | Retry | Max Attempts | Alert |
|------------|-------|-------|--------------|-------|
| Connection timeout | Retry | Yes | 3 | Yes (after 3) |
| Authentication fail | Stop processor | No | — | Critical |
| Schema validation fail | DLQ | No | — | Warning |
| Payload too large | DLQ + Log | No | — | Warning |
| Kafka publish fail | Retry | Yes | 5 | Yes (after 5) |
| Source unavailable | Backoff retry | Yes | ∞ (with backoff) | Warning |

---

## 5. Validation Processor

### 5.1 Validation Rules

| Rule | Type | Severity | Description |
|------|------|----------|-------------|
| Schema compliance | Structural | Critical | Event matches JSON Schema |
| Mandatory fields | Completeness | Critical | event_id, timestamp, source_system, event_type, payload present |
| Data type check | Type | High | Each field matches expected type |
| Range validation | Logical | High | Numeric values within expected range |
| Format validation | Format | Medium | Timestamp ISO 8601, UUID format, enum values |
| Duplicate detection | Uniqueness | Medium | event_id + source_system unique within 5min window |
| Freshness check | Temporal | Low | timestamp not older than 24h |
| Source validation | Security | Critical | source_system in allowed list |

### 5.2 Validation Implementation

```python
# processors/validation.py

from jsonschema import validate, ValidationError
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import hashlib

class EventValidator:
    def __init__(self, schema: dict, redis_client):
        self.schema = schema
        self.redis = redis_client
        self.duplicate_window = 300  # 5 minutes
    
    def validate(self, event: Dict[str, Any]) -> Tuple[bool, list, str]:
        """
        Validate event against all rules.
        Returns: (is_valid, errors, rejection_reason)
        """
        errors = []
        
        # 1. Schema compliance
        try:
            validate(instance=event, schema=self.schema)
        except ValidationError as e:
            errors.append(f"Schema violation: {e.message}")
            return False, errors, "schema_violation"
        
        # 2. Mandatory fields
        required = ["event_id", "timestamp", "source_system", "event_type", "payload"]
        for field in required:
            if field not in event or event[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # 3. Data type checks
        if not isinstance(event.get("event_id"), str):
            errors.append("event_id must be string")
        
        # 4. Timestamp freshness
        try:
            ts = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
            if ts < datetime.now(ts.tzinfo) - timedelta(hours=24):
                errors.append(f"Event too old: {event['timestamp']}")
        except (ValueError, AttributeError):
            errors.append(f"Invalid timestamp format: {event.get('timestamp')}")
        
        # 5. Duplicate detection
        dedup_key = f"dedup:{event['event_id']}:{event['source_system']}"
        if self.redis.exists(dedup_key):
            errors.append(f"Duplicate event: {event['event_id']}")
        else:
            self.redis.setex(dedup_key, self.duplicate_window, "1")
        
        # 6. Source validation
        allowed_sources = [
            "bms", "epms", "ems", "nms",
            "server_monitor", "storage_monitor",
            "vmware", "aws", "gcp", "azure",
            "access_control", "surveillance",
            "itsm", "erp", "dms", "manual", "api"
        ]
        if event.get("source_system") not in allowed_sources:
            errors.append(f"Unknown source_system: {event.get('source_system')}")
        
        is_valid = len(errors) == 0
        reason = "none" if is_valid else errors[0].split(":")[0]
        
        return is_valid, errors, reason
```

### 5.3 Validation Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `dii_validation_total` | Counter | Total events validated |
| `dii_validation_passed` | Counter | Events passed validation |
| `dii_validation_rejected` | Counter | Events rejected |
| `dii_validation_duration_seconds` | Histogram | Validation latency |
| `dii_validation_errors_by_reason` | Counter | Rejection reason breakdown |
| `dii_validation_duplicates_total` | Counter | Duplicate events detected |

---

## 6. Enrichment Processor

### 6.1 Enrichment Sources

| Source | Method | Latency | Cache TTL |
|--------|--------|---------|-----------|
| CMDB CI lookup | REST API / Direct DB | < 10ms | 5 min |
| Asset Repository lookup | REST API / Direct DB | < 10ms | 5 min |
| Location mapping | Redis cache | < 1ms | 30 min |
| Priority assignment | Rule engine | < 1ms | — |
| Impact scoring | Rule engine | < 5ms | — |

### 6.2 Enrichment Rules

```yaml
# enrichment-rules.yaml

rules:
  # Priority assignment based on event_type and severity
  - name: critical_alarm_priority
    condition:
      event_type: "*.alarm"
      payload.severity: "critical"
    action:
      set_priority: "P1"
      set_impact_score: 9

  - name: warning_alarm_priority
    condition:
      event_type: "*.alarm"
      payload.severity: "warning"
    action:
      set_priority: "P2"
      set_impact_score: 6

  # Location enrichment from device_id
  - name: location_from_device
    condition:
      payload.device_id: exists
    action:
      lookup: "device_location"
      source: "asset_repository"
      target_fields:
        - "enrichment.location.site"
        - "enrichment.location.building"
        - "enrichment.location.floor"
        - "enrichment.location.room"
        - "enrichment.location.rack"

  # CI enrichment from device_id
  - name: ci_from_device
    condition:
      payload.device_id: exists
    action:
      lookup: "device_ci_mapping"
      source: "cmdb"
      target_fields:
        - "enrichment.ci_id"
        - "enrichment.asset_id"
```

### 6.3 Enrichment Implementation

```python
# processors/enrichment.py

from typing import Dict, Any
import redis
import json

class EventEnricher:
    def __init__(self, cmdb_client, asset_client, redis_client):
        self.cmdb = cmdb_client
        self.asset = asset_client
        self.redis = redis_client
    
    def enrich(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich event with CI, location, and priority metadata."""
        
        device_id = event.get("payload", {}).get("device_id")
        
        # 1. CI lookup (with cache)
        if device_id:
            ci_data = self._lookup_ci(device_id)
            if ci_data:
                event["enrichment"] = event.get("enrichment", {})
                event["enrichment"]["ci_id"] = ci_data["ci_id"]
                event["enrichment"]["asset_id"] = ci_data.get("asset_id")
                event["enrichment"]["location"] = ci_data.get("location")
        
        # 2. Priority assignment (if not already set)
        if not event.get("metadata", {}).get("priority"):
            event["metadata"]["priority"] = self._assign_priority(event)
        
        # 3. Impact scoring
        event["enrichment"] = event.get("enrichment", {})
        event["enrichment"]["impact_score"] = self._calculate_impact(event)
        event["enrichment"]["enriched_at"] = datetime.utcnow().isoformat() + "Z"
        
        return event
    
    def _lookup_ci(self, device_id: str) -> dict:
        """Look up CI data from CMDB with Redis cache."""
        cache_key = f"enrich:ci:{device_id}"
        
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Query CMDB
        ci_data = self.cmdb.get_ci_by_device_id(device_id)
        if ci_data:
            self.redis.setex(cache_key, 300, json.dumps(ci_data))  # 5 min cache
        
        return ci_data
    
    def _assign_priority(self, event: dict) -> str:
        """Assign priority based on event rules."""
        event_type = event.get("event_type", "")
        severity = event.get("payload", {}).get("severity", "")
        
        if severity == "critical" or "alarm" in event_type:
            return "P1"
        elif severity == "warning":
            return "P2"
        elif "metrics" in event_type:
            return "P3"
        else:
            return "P4"
    
    def _calculate_impact(self, event: dict) -> float:
        """Calculate impact score (0-10)."""
        base = 5.0
        
        # Priority adjustment
        priority = event.get("metadata", {}).get("priority", "P3")
        priority_adj = {"P1": 4, "P2": 2, "P3": 0, "P4": -2}
        base += priority_adj.get(priority, 0)
        
        # CI criticality adjustment
        ci_criticality = event.get("enrichment", {}).get("ci_criticality", "medium")
        criticality_adj = {"critical": 2, "high": 1, "medium": 0, "low": -1}
        base += criticality_adj.get(ci_criticality, 0)
        
        return max(0, min(10, base))
```

---

## 7. DLQ Handling

### 7.1 DLQ Flow

```
Failed Event → Kafka dlq topic → DLQ Consumer → Analyze → Retry/Discard
                                        │
                                        ├── Retry (if transient error)
                                        │   └── Re-publish to original topic
                                        │
                                        ├── Archive (if permanent error)
                                        │   └── Store to S3/MinIO + log
                                        │
                                        └── Alert (if threshold exceeded)
                                            └── Slack/Email notification
```

### 7.2 DLQ Event Structure

```json
{
  "event_id": "original-event-id",
  "original_topic": "dcim.events.raw",
  "failure_timestamp": "2026-06-23T14:30:00.000Z",
  "failure_reason": "schema_violation",
  "failure_details": {
    "validator": "schema_check",
    "error_message": "Missing required field: payload.device_id",
    "attempt_count": 3,
    "last_attempt_at": "2026-06-23T14:30:05.000Z"
  },
  "original_event": {
    "... original event payload ..."
  },
  "retry_config": {
    "max_retries": 3,
    "retry_count": 1,
    "next_retry_at": "2026-06-23T14:35:00.000Z",
    "backoff_ms": 60000
  }
}
```

### 7.3 Retry Strategy

| Failure Type | Max Retries | Backoff | Action After Max |
|-------------|-------------|---------|-----------------|
| Schema violation | 0 | — | Archive + Alert |
| Connection timeout | 5 | Exponential (1s → 32s) | Archive + Alert |
| Kafka unavailable | 10 | Exponential (5s → 5min) | Archive + Alert |
| Enrichment unavailable | 3 | Linear (30s) | Pass without enrichment |
| Unknown | 3 | Exponential (1s → 8s) | Archive + Alert |

### 7.4 DLQ Monitoring

```yaml
# DLQ alert rules
alerts:
  - name: dlq_growth_rate
    condition: rate(dcim_dlq_messages_total[5m]) > 10
    severity: warning
    message: "DLQ growing at {{ $value }} msg/sec"

  - name: dlq_total_threshold
    condition: dcim_dlq_messages_total > 1000
    severity: critical
    message: "DLQ has {{ $value }} unprocessed messages"

  - name: dlq_age
    condition: dcim_dlq_oldest_message_age_seconds > 3600
    severity: warning
    message: "DLQ oldest message is {{ $value }}s old"
```

---

## 8. Data Lineage Tracking

### 8.1 Lineage Model

```
Event Lineage:
  source → raw_ingest → validation → enrichment → routing → store

Every event gets:
  - lineage_id (UUID)
  - parent_lineage_id (for derived events)
  - timestamps at each stage
  - processing_status at each stage
  - error details if failed at any stage
```

### 8.2 Lineage Storage Schema

```sql
-- PostgreSQL: dcim_lineage database

CREATE TABLE event_lineage (
    lineage_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    
    -- Stage timestamps
    ingested_at TIMESTAMPTZ NOT NULL,
    validated_at TIMESTAMPTZ,
    enriched_at TIMESTAMPTZ,
    routed_at TIMESTAMPTZ,
    stored_at TIMESTAMPTZ,
    
    -- Stage status
    validation_status VARCHAR(20) DEFAULT 'pending',
    enrichment_status VARCHAR(20) DEFAULT 'pending',
    routing_status VARCHAR(20) DEFAULT 'pending',
    
    -- Target store
    target_store VARCHAR(50),
    target_id VARCHAR(255),
    
    -- Error tracking
    error_stage VARCHAR(20),
    error_message TEXT,
    error_timestamp TIMESTAMPTZ,
    
    -- Metadata
    processing_duration_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT valid_status CHECK (validation_status IN ('pending', 'passed', 'failed', 'skipped')),
    CONSTRAINT valid_enrichment CHECK (enrichment_status IN ('pending', 'completed', 'skipped', 'failed')),
    CONSTRAINT valid_routing CHECK (routing_status IN ('pending', 'completed', 'failed'))
);

CREATE INDEX idx_lineage_event_id ON event_lineage(event_id);
CREATE INDEX idx_lineage_source ON event_lineage(source_system);
CREATE INDEX idx_lineage_ingested ON event_lineage(ingested_at);
CREATE INDEX idx_lineage_status ON event_lineage(validation_status, enrichment_status, routing_status);

-- Partition by month for performance
CREATE TABLE event_lineage_2026_06 PARTITION OF event_lineage
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

### 8.3 Lineage Tracking Implementation

```python
# processors/lineage.py

from datetime import datetime
from typing import Optional
import uuid

class LineageTracker:
    def __init__(self, db_pool):
        self.db = db_pool
    
    async def create_lineage(self, event_id: str, source_system: str) -> str:
        """Create new lineage record when event is ingested."""
        lineage_id = str(uuid.uuid4())
        
        await self.db.execute("""
            INSERT INTO event_lineage (lineage_id, event_id, source_system, ingested_at)
            VALUES ($1, $2, $3, $4)
        """, lineage_id, event_id, source_system, datetime.utcnow())
        
        return lineage_id
    
    async def update_validation(self, lineage_id: str, status: str, error: Optional[str] = None):
        """Update validation stage."""
        await self.db.execute("""
            UPDATE event_lineage 
            SET validation_status = $1, validated_at = $2, 
                error_stage = CASE WHEN $1 = 'failed' THEN 'validation' ELSE error_stage END,
                error_message = $3
            WHERE lineage_id = $4
        """, status, datetime.utcnow(), error, lineage_id)
    
    async def update_enrichment(self, lineage_id: str, status: str, error: Optional[str] = None):
        """Update enrichment stage."""
        await self.db.execute("""
            UPDATE event_lineage 
            SET enrichment_status = $1, enriched_at = $2,
                error_stage = CASE WHEN $1 = 'failed' THEN 'enrichment' ELSE error_stage END,
                error_message = $3
            WHERE lineage_id = $4
        """, status, datetime.utcnow(), error, lineage_id)
    
    async def update_routing(self, lineage_id: str, target_store: str, target_id: str):
        """Update routing stage."""
        await self.db.execute("""
            UPDATE event_lineage 
            SET routing_status = 'completed', routed_at = $1,
                target_store = $2, target_id = $3, stored_at = $1
            WHERE lineage_id = $4
        """, datetime.utcnow(), target_store, target_id, lineage_id)
```

---

## 9. ITSM/ERP/DMS Connectors

### 9.1 Connector Architecture

```
┌─────────────────────────────────────────────────────┐
│              Adapter Pattern Framework               │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ ITSM     │  │ ERP      │  │ DMS      │          │
│  │ Connector│  │ Connector│  │ Connector│          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │              │              │                │
│  ┌────┴──────────────┴──────────────┴─────┐         │
│  │           Base Connector               │         │
│  │  - Auth (OAuth2, API Key, Basic)       │         │
│  │  - Rate limiting                       │         │
│  │  - Retry with backoff                  │         │
│  │  - Circuit breaker                     │         │
│  │  - Transform to DCIM event schema      │         │
│  └────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────┘
```

### 9.2 ITSM Connector

| System | Protocol | Auth | Sync Direction |
|--------|----------|------|----------------|
| ServiceNow | REST API | OAuth2 | Bidirectional |
| Jira | REST API | API Key | Bidirectional |

#### ServiceNow Integration

```python
# connectors/itsm/servicenow.py

class ServiceNowConnector(BaseConnector):
    def __init__(self, config):
        super().__init__(config)
        self.base_url = config["snow_url"]
        self.auth = OAuth2Auth(config["client_id"], config["client_secret"])
    
    async def sync_incidents(self) -> list:
        """Sync incidents from ServiceNow to DCIM events."""
        incidents = await self.get("/api/now/table/incident", params={
            "sysparm_query": "sys_updated_on>javascript:gs.hoursAgoStart(1)",
            "sysparm_fields": "number,short_description,severity,state,assigned_to",
            "sysparm_limit": 100
        })
        
        events = []
        for inc in incidents:
            event = self._transform_to_event(inc)
            events.append(event)
        
        return events
    
    def _transform_to_event(self, incident: dict) -> dict:
        """Transform ServiceNow incident to DCIM event."""
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": incident["sys_updated_on"],
            "source_system": "itsm",
            "event_type": "ticket.itsm.incident_update",
            "payload": {
                "ticket_number": incident["number"],
                "title": incident["short_description"],
                "severity": incident["severity"],
                "state": incident["state"],
                "assignee": incident["assigned_to"],
                "system": "servicenow"
            },
            "metadata": {
                "priority": self._map_priority(incident["severity"]),
                "category": "availability",
                "tags": ["itsm", "incident"]
            }
        }
    
    async def create_ticket(self, event: dict) -> str:
        """Create ticket in ServiceNow from DCIM event."""
        payload = {
            "short_description": event["payload"].get("title", "DCIM Alert"),
            "description": self._format_description(event),
            "severity": self._map_severity(event["metadata"]["priority"]),
            "category": "hardware"
        }
        
        result = await self.post("/api/now/table/incident", json=payload)
        return result["number"]
```

### 9.3 ERP Connector

| System | Protocol | Auth | Data |
|--------|----------|------|------|
| SAP | RFC/BAPI | SSO | Asset financial data |
| Oracle | REST API | OAuth2 | Asset financial data |

### 9.4 DMS Connector

| System | Protocol | Auth | Data |
|--------|----------|------|------|
| Custom DMS | REST API | API Key | Documents, manuals, certificates |

### 9.5 Circuit Breaker

```python
# connectors/base.py

from circuitbreaker import circuit

class BaseConnector:
    @circuit(failure_threshold=5, recovery_timeout=60)
    async def request(self, method, url, **kwargs):
        """Make request with circuit breaker."""
        response = await self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
```

---

## 10. Data Quality Framework

### 10.1 Quality Dimensions

| Dimension | Metric | Target | Measurement |
|-----------|--------|--------|-------------|
| Completeness | Mandatory field fill rate | > 99.9% | Validation processor |
| Accuracy | Schema compliance rate | > 99.5% | Validation processor |
| Timeliness | Event age at ingestion | < 30s (real-time) | Timestamp comparison |
| Uniqueness | Duplicate rate | < 0.1% | Dedup processor |
| Consistency | Schema version compliance | 100% | Schema registry |
| Validity | Range/format check pass rate | > 99% | Validation processor |

### 10.2 Quality Scorecard

```sql
-- Daily quality scorecard
CREATE VIEW daily_quality_scorecard AS
SELECT 
    DATE(ingested_at) as date,
    source_system,
    COUNT(*) as total_events,
    COUNT(*) FILTER (WHERE validation_status = 'passed') as passed,
    COUNT(*) FILTER (WHERE validation_status = 'failed') as failed,
    ROUND(100.0 * COUNT(*) FILTER (WHERE validation_status = 'passed') / COUNT(*), 2) as pass_rate,
    COUNT(*) FILTER (WHERE enrichment_status = 'completed') as enriched,
    ROUND(100.0 * COUNT(*) FILTER (WHERE enrichment_status = 'completed') / COUNT(*), 2) as enrichment_rate,
    AVG(processing_duration_ms) as avg_processing_ms
FROM event_lineage
WHERE ingested_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE(ingested_at), source_system
ORDER BY date DESC, source_system;
```

---

## 11. Error Handling Strategy

### 11.1 Error Classification

| Category | Examples | Handling | Alert |
|----------|----------|----------|-------|
| Transient | Network timeout, Kafka unavailable | Retry with backoff | After max retries |
| Permanent | Schema violation, auth failure | DLQ + Archive | Immediate |
| Degraded | Enrichment unavailable | Pass without enrichment | Warning |
| Critical | Data corruption, security breach | Stop pipeline + Alert | Critical |

### 11.2 Error Handling Flow

```
Error Detected
    │
    ├── Transient? → Retry (exponential backoff)
    │                   │
    │                   ├── Success → Continue
    │                   └── Max retries → DLQ + Alert
    │
    ├── Permanent? → DLQ + Archive + Alert
    │
    ├── Degraded? → Continue with degraded mode
    │
    └── Critical? → Stop pipeline + Critical Alert
```

---

## 12. Performance & Sizing

### 12.1 Throughput Requirements

| Source | Events/sec | Batch Size | Latency Target |
|--------|------------|------------|----------------|
| BMS/EPMS | 100 | 50 | < 5s |
| NMS | 50 | 100 | < 5s |
| Server/Storage | 200 | 200 | < 10s |
| Virtualization/Cloud | 50 | 50 | < 30s |
| Access Control | 30 | 100 | < 5s |
| **Total** | **430** | — | **< 10s avg** |

### 12.2 Processing Capacity

| Component | Throughput | Resource | Bottleneck |
|-----------|------------|----------|------------|
| NiFi | 1000 events/s per flow | 2 vCPU, 4GB RAM | Network I/O |
| Validation | 5000 events/s | 1 vCPU, 2GB RAM | CPU |
| Enrichment | 2000 events/s | 1 vCPU, 2GB RAM | Redis latency |
| Kafka Producer | 10000 events/s | Network | Network |
| Kafka Consumer | 5000 events/s per group | Network | Network |

### 12.3 Resource Allocation

| Component | vCPU | RAM | Storage | Instances |
|-----------|------|-----|---------|-----------|
| NiFi | 2 | 4 GB | 50 GB SSD | 2 (HA) |
| Validation Worker | 1 | 2 GB | — | 3 |
| Enrichment Worker | 1 | 2 GB | — | 3 |
| DLQ Monitor | 1 | 1 GB | — | 1 |
| Lineage Writer | 1 | 2 GB | 20 GB SSD | 2 |
| ITSM/ERP Connectors | 1 | 1 GB | — | 2 |
| **Total** | **~12** | **~20 GB** | **~90 GB** | **~13** |

---

## 13. Security

### 13.1 Data Classification

| Data Type | Classification | Handling |
|-----------|---------------|----------|
| Event payload (metrics) | Internal | Standard encryption |
| Event payload (security events) | Confidential | AES-256, access control |
| Event payload (PII) | Restricted | Masking, tokenization |
| Credentials (in transit) | Secret | TLS 1.2+, Vault |

### 13.2 Security Controls

| Control | Implementation | Scope |
|---------|---------------|-------|
| Encryption in transit | TLS 1.2+ | All Kafka, NiFi, API traffic |
| Encryption at rest | AES-256 | DLQ archives, lineage storage |
| Authentication | mTLS + API Key | NiFi → Kafka, Connectors → External |
| Authorization | RBAC | NiFi policies, Kafka ACLs |
| Audit trail | Lineage tracking | Every event, every stage |
| Input validation | Schema validation | Every event at ingestion |
| Rate limiting | Token bucket | Per source system |
| Circuit breaker | Per connector | External system calls |

### 13.3 Kafka ACLs

```bash
# Create ACLs for DI&I topics
kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --allow-principal User:dii-producer \
  --operation Write --topic dcim.events.raw

kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --allow-principal User:dii-consumer \
  --operation Read --topic dcim.events.raw

kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --allow-principal User:dii-consumer \
  --operation Read --topic dcim.events.validated

# Deny all other access
kafka-acls.sh --bootstrap-server kafka:9092 \
  --add --deny-principal User:* --operation All --topic dcim.events.*
```

---

## 14. Monitoring & Alerting

### 14.1 Key Metrics

| Metric | Type | Labels | Threshold |
|--------|------|--------|-----------|
| `dii_events_ingested_total` | Counter | source_system | — |
| `dii_events_validated_total` | Counter | source_system, status | — |
| `dii_events_enriched_total` | Counter | source_system | — |
| `dii_events_routed_total` | Counter | target_store | — |
| `dii_validation_latency_seconds` | Histogram | source_system | p99 < 100ms |
| `dii_enrichment_latency_seconds` | Histogram | source_system | p99 < 50ms |
| `dii_dlq_messages_total` | Gauge | source_system | < 100 |
| `dii_dlq_growth_rate` | Gauge | source_system | < 10/min |
| `dii_kafka_consumer_lag` | Gauge | consumer_group, topic | < 10000 |
| `dii_lineage_processing_duration_seconds` | Histogram | — | p99 < 1s |

### 14.2 Alert Rules

```yaml
groups:
  - name: dii-ingestion
    rules:
      - alert: DIIEingestionRateDrop
        expr: rate(dii_events_ingested_total[5m]) < 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DI&I ingestion rate dropped below 10 eps"

      - alert: DIIDLQGrowthHigh
        expr: rate(dii_dlq_messages_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DLQ growing at {{ $value }} msg/sec"

      - alert: DIIDLQThresholdExceeded
        expr: dii_dlq_messages_total > 1000
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "DLQ has {{ $value }} unprocessed messages"

      - alert: DIIValidationLatencyHigh
        expr: histogram_quantile(0.99, rate(dii_validation_latency_seconds_bucket[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Validation p99 latency > 100ms"

      - alert: DIIEinrichmentLatencyHigh
        expr: histogram_quantile(0.99, rate(dii_enrichment_latency_seconds_bucket[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Enrichment p99 latency > 50ms"

      - alert: DIIEKafkaConsumerLagHigh
        expr: dii_kafka_consumer_lag > 10000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Kafka consumer lag > 10k on {{ $labels.consumer_group }}"
```

---

## 15. Acceptance Criteria — Block 2 Complete

| # | Criterion | Evidence | Status |
|---|-----------|----------|--------|
| 1 | Event schema defined | `event-schema.json` + JSON Schema validator passes | ⬜ |
| 2 | Event type taxonomy complete | 9 namespaces, 25+ event types defined | ⬜ |
| 3 | Kafka topics created | 10 topics, RF=3, min.insync=2 | ⬜ |
| 4 | NiFi BMS flow operational | Flow imports, processes test events | ⬜ |
| 5 | NiFi NMS flow operational | Flow imports, processes SNMP data | ⬜ |
| 6 | NiFi Server/Storage flow operational | Flow imports, processes metrics | ⬜ |
| 7 | NiFi Cloud/VM flow operational | Flow imports, processes VM data | ⬜ |
| 8 | NiFi Access Control flow operational | Flow imports, processes badge data | ⬜ |
| 9 | Validation processor working | Rejects invalid events, passes valid | ⬜ |
| 10 | Enrichment processor working | Adds CI, location, priority metadata | ⬜ |
| 11 | DLQ handling working | Failed events routed, retry works | ⬜ |
| 12 | Data lineage tracking | Every event tracked through pipeline | ⬜ |
| 13 | ITSM connector (ServiceNow) | Creates/updates tickets from events | ⬜ |
| 14 | ERP connector (SAP/Oracle) | Syncs asset financial data | ⬜ |
| 15 | DMS connector | Syncs documents/manuals | ⬜ |
| 16 | End-to-end flow test | Source → NiFi → Kafka → Validate → Enrich → Store | ⬜ |
| 17 | Performance target met | 430 eps sustained, p99 < 1s | ⬜ |
| 18 | Security controls enforced | TLS, ACLs, auth working | ⬜ |
| 19 | Monitoring dashboards | Grafana shows DI&I metrics | ⬜ |
| 20 | Alert rules active | Test alert fires correctly | ⬜ |

---

## 17. NVR Connector Flows

> **Full spec:** `nvr-asset-repository-integration.md`
> **Architecture diagram:** `diagrams/nvr-asset-repository-integration.html`

### 17.1 NVR Event Types

| Namespace | Category | Actions | Example |
|-----------|----------|---------|---------|
| `security` | `nvr` | `discovery`, `health`, `events` | `security.nvr.discovery` |
| `security` | `nvr` | `camera_offline`, `disk_full` | `security.nvr.camera_offline` |
| `security` | `nvr` | `location_verify` | `security.nvr.location_verify` |

### 17.2 NVR Kafka Topics

| Topic | Partitions | Retention | Purpose |
|-------|-----------|-----------|---------|
| `dcim.nvr.discovery` | 3 | 7 days | ONVIF probe results |
| `dcim.nvr.health` | 6 | 3 days | SNMP polling metrics |
| `dcim.nvr.events` | 6 | 30 days | Syslog events |
| `dcim.nvr.cameras` | 3 | 7 days | Camera registry sync |
| `dcim.nvr.location` | 3 | 30 days | Location validation events |

### 17.3 NiFi Flow Summary

| Flow | Input | Protocol | Output Topic |
|------|-------|----------|-------------|
| ONVIF Discovery | Timer (24h) | WS-Discovery | `dcim.nvr.discovery` |
| SNMP Health | Timer (5min) | SNMPv3 | `dcim.nvr.health` |
| Syslog Events | UDP :5140 | Syslog/CEF | `dcim.nvr.events` |
| Camera Registry | ONVIF | ONVIF Profiles | `dcim.nvr.cameras` |
| Asset Sync | Kafka Consumer | REST API | Asset DB (PostgreSQL) |

---

## 18. Gap Comparison Template

### Gap: [Component Name]

| Aspect | Reference Design | Actual Implementation | Gap | Priority |
|--------|-----------------|----------------------|-----|----------|
| Schema | [spec detail] | [aktual detail] | [match/mismatch] | P1-P4 |
| Kafka config | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| NiFi flow | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| Validation | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| Enrichment | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| DLQ handling | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| Lineage | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| Connectors | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| Security | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |
| Monitoring | [spec detail] | [aktual detail] | [gap detail] | P1-P4 |

**Decision:** [adopt spec / keep actual / hybrid]
**Rationale:** [why]
**Action items:** [what to do]

---

## References

- [[data-ingestion-integration]]
- [[kafka]]
- [[nifi]]
- [[data-quality-runbook]]
- [[dcim-data-flow-architecture]]
- [[cmdb]] — receives CI updates
- [[asset-repository]] — receives asset updates
- [[dcim-core-platform]]

---

> **Status:** Generated by Hermes DCIM Orchestrator
> **Date:** 2026-06-23
> **Purpose:** Reference for team comparison → gap identification → connection dots
> **Block 1 Reference:** `block1-infrastructure-provisioning.md` — infra components yang digunakan DI&I
