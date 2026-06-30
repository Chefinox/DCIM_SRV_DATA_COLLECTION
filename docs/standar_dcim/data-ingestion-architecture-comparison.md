---
title: "Data Ingestion Architecture Comparison"
created: 2026-06-25
updated: 2026-06-25
type: comparison
tags: [data-ingestion, architecture, lambda, kappa, kafka, nifi, flink, comparison]
sources:
  - block2-data-ingestion-integration
  - data-integration-comparison
  - data-pipeline-comparison
confidence: high
purpose: >
  Perbandingan mendalam arsitektur data ingestion untuk DCIM platform.
  Mencakup architecture patterns, technology stacks, deployment patterns,
  dan trade-offs untuk setiap pendekatan.
---

# Data Ingestion Architecture Comparison

> **Purpose:** Perbandingan komprehensif arsitektur data ingestion untuk membantu tim memilih pendekatan yang tepat berdasarkan kebutuhan DCIM.
> **Cara pakai:** Review setiap section, identifikasi kebutuhan DCIM, gunakan recommendation matrix untuk keputusan.
> **Related:** [[data-ingestion-integration]], [[block2-data-ingestion-integration]]

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Pattern Comparison](#2-architecture-pattern-comparison)
3. [Technology Stack Comparison](#3-technology-stack-comparison)
4. [Deployment Pattern Comparison](#4-deployment-pattern-comparison)
5. [Processing Mode Analysis](#5-processing-mode-analysis)
6. [DCIM Source Systems Matrix](#6-dcim-source-systems-matrix)
7. [Recommendation Matrix](#7-recommendation-matrix)
8. [Gap Comparison Template](#8-gap-comparison-template)

---

## 1. Executive Summary

### Key Decision Points

| Decision | Options | DCIM Impact |
|----------|---------|-------------|
| Architecture Pattern | Lambda / Kappa / Event-Driven / Hybrid | Complexity, latency, replay capability |
| Technology Stack | NiFi+Kafka / Kafka-native / Pulsar / Camel / Custom | Operational overhead, flexibility |
| Deployment | Centralized / Distributed / Hybrid | Latency, scalability, management |
| Processing Mode | Real-time / Near-RT / Batch / Mixed | SLA compliance, resource usage |

### Quick Recommendation for DCIM

**Hybrid Architecture + NiFi/Kafka/Flink Stack + Centralized Gateway**

Rationale:
- DCIM has diverse sources (BMS, NMS, server, cloud, access control)
- Mixed SLA requirements (P1 real-time alerts vs P4 batch reports)
- Need for data quality (validation, enrichment, lineage)
- Operational simplicity preferred over theoretical purity

---

## 2. Architecture Pattern Comparison

### 2.1 Lambda Architecture

```
                    ┌─────────────────┐
                    │   Batch Layer   │
                    │ (Historical)    │
                    └────────┬────────┘
                             │
Source ──→ ┌─────────────────┴─────────────────┐
           │           Speed Layer              │
           │       (Real-time Processing)       │
           └─────────────────┬─────────────────┘
                             │
                    ┌────────┴────────┐
                    │  Serving Layer  │
                    │ (Merged View)   │
                    └─────────────────┘
```

**Characteristics:**
- Two parallel processing paths (batch + real-time)
- Batch layer provides comprehensive, accurate views
- Speed layer provides low-latency, approximate views
- Serving layer merges both for query

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Fault Tolerance | Batch layer can recompute from raw data |
| Accuracy | Batch processing ensures completeness |
| Flexibility | Different tools for different latency needs |
| Replay | Can reprocess historical data |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Complexity | Two codebases to maintain |
| Consistency | May have temporary inconsistencies between layers |
| Operational Overhead | More infrastructure to manage |
| Code Duplication | Logic often duplicated across layers |

**DCIM Fit:** ⭐⭐⭐ (Good)
- Batch layer handles historical sync and reconciliation
- Speed layer handles real-time alerts (P1/P2)
- Complexity justified by diverse SLA requirements

---

### 2.2 Kappa Architecture

```
                    ┌─────────────────┐
                    │  Message Broker │
                    │ (Event Log)     │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │ Stream Processor│
                    │ (Single Path)   │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │  Views/State    │
                    └─────────────────┘
```

**Characteristics:**
- Single processing path (stream-only)
- All data treated as events in a log
- Reprocessing by replaying the log
- No separate batch layer

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Simplicity | Single codebase, single path |
| Consistency | No divergence between batch and real-time |
| Reprocessing | Replay log for corrections |
| Lower Operations | Fewer components to manage |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Log Retention | Need long retention for reprocessing |
| Processing Power | Stream processor must handle all workloads |
| Complexity | Complex state management for large-scale |
| Batch Efficiency | Less efficient for bulk operations |

**DCIM Fit:** ⭐⭐ (Moderate)
- Simpler operations appeal
- But DCIM has legitimate batch use cases (nightly reconciliation, bulk imports)
- Log retention for 90+ days of 430 eps = significant storage

---

### 2.3 Event-Driven Architecture (Pure)

```
                    ┌─────────────────┐
                    │  Event Bus      │
                    │ (Pub/Sub)       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
        │ Consumer A│ │ Consumer B│ │ Consumer C│
        └───────────┘ └───────────┘ └───────────┘
```

**Characteristics:**
- Decoupled producers and consumers
- Event choreography (no central orchestrator)
- Each service owns its data
- Asynchronous communication

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Decoupling | Services can evolve independently |
| Scalability | Each consumer scales independently |
| Flexibility | Easy to add new consumers |
| Resilience | Failure in one consumer doesn't affect others |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Visibility | Hard to trace end-to-end flow |
| Ordering | Complex event ordering across services |
| Debugging | Difficult to troubleshoot |
| Data Consistency | Eventual consistency challenges |

**DCIM Fit:** ⭐⭐ (Moderate)
- Good for downstream consumers (CMDB, Asset, SIEM)
- But DCIM needs centralized validation/enrichment
- Event choreography makes data quality enforcement harder

---

### 2.4 Hybrid Architecture (Recommended)

```
                    ┌─────────────────────────────────────────┐
                    │           DI&I Gateway                  │
                    │  ┌───────────┐    ┌──────────────────┐ │
                    │  │ Validate  │───→│ Enrich           │ │
                    │  │ & Cleanse │    │ (CI, Location)   │ │
                    │  └───────────┘    └──────────────────┘ │
                    └───────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────┴─────────────────────┐
                    │              Kafka                      │
                    │  ┌─────┐  ┌─────────┐  ┌───────────┐  │
                    │  │ Raw │  │Validated│  │ Enriched  │  │
                    │  └─────┘  └─────────┘  └───────────┘  │
                    └───────────────────┬─────────────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         │                              │                              │
   ┌─────┴─────┐                ┌───────┴───────┐              ┌───────┴───────┐
   │Real-time  │                │  Near-RT      │              │    Batch      │
   │(<1s)      │                │  (1-30s)      │              │   (min-hrs)   │
   │Flink/KS   │                │  Kafka Cons.  │              │  NiFi sched.  │
   └─────┬─────┘                └───────┬───────┘              └───────┬───────┘
         │                              │                              │
   ┌─────┴─────┐                ┌───────┴───────┐              ┌───────┴───────┐
   │ SIEM/Alert│                │ CMDB/Asset    │              │ Analytics     │
   │ (P1/P2)   │                │ (P2/P3)       │              │ (P3/P4)       │
   └───────────┘                └───────────────┘              └───────────────┘
```

**Characteristics:**
- Centralized DI&I gateway for data quality
- Multiple processing paths based on SLA
- Kafka as unified event backbone
- Different tools for different latency needs

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Pragmatic | Matches real-world DCIM requirements |
| SLA Compliance | Right tool for each latency requirement |
| Data Quality | Centralized validation/enrichment |
| Flexibility | Can evolve paths independently |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Complexity | Multiple processing paths |
| Operational Overhead | NiFi + Kafka + Flink to manage |
| Skill Requirements | Team needs multiple technology skills |

**DCIM Fit:** ⭐⭐⭐⭐⭐ (Excellent)
- Matches DCIM's diverse source systems
- Supports mixed SLA requirements (P1-P4)
- Centralized data quality enforcement
- Pragmatic approach over theoretical purity

---

## 3. Technology Stack Comparison

### 3.1 Stack Options

| Stack | Components | Complexity | Flexibility |
|-------|-----------|------------|-------------|
| **A: NiFi+Kafka+Flink** | NiFi (ingest), Kafka (backbone), Flink (stream) | Medium-High | High |
| **B: Kafka-native** | Kafka Connect (ingest), Kafka Streams (process) | Medium | Medium |
| **C: Pulsar+Functions** | Pulsar (msg), Pulsar Functions (compute) | Medium | Medium-High |
| **D: Camel+Kafka** | Camel (integration), Kafka (backbone) | Medium | High |
| **E: Custom Python/Go** | Custom ingest, Kafka (backbone), Python (process) | Low-Medium | Low |

### 3.2 Stack A: NiFi + Kafka + Flink (Current Reference Design)

**Architecture:**
```
Sources → NiFi (ingest) → Kafka → Flink (real-time) → Sinks
                         ↓
                    Kafka consumers (NRT/batch)
```

**Pros:**
| Aspect | Detail |
|--------|--------|
| Visual Design | NiFi provides drag-and-drop flow design |
| Protocol Support | NiFi has 100+ processors for various protocols |
| Scalability | Kafka + Flink scale horizontally |
| Maturity | All components are Apache top-level projects |
| DCIM Fit | NiFi handles BMS/Modbus/SNMP, Flink handles real-time |

**Cons:**
| Aspect | Detail |
|--------|--------|
| Operational Complexity | 3 separate systems to manage |
| Resource Usage | Flink + NiFi + Kafka = significant footprint |
| Learning Curve | Team needs NiFi + Kafka + Flink skills |
| Debugging | Tracing across 3 systems is challenging |

**Best For:** DCIM with diverse sources, mixed SLA, need for visual design

---

### 3.3 Stack B: Kafka-native (Connect + Streams)

**Architecture:**
```
Sources → Kafka Connect (ingest) → Kafka → Kafka Streams (process) → Sinks
```

**Pros:**
| Aspect | Detail |
|--------|--------|
| Simplicity | Single ecosystem (Kafka) |
| Consistency | No data movement between systems |
| Scalability | Connect + Streams scale with Kafka |
| Operational | One system to manage |

**Cons:**
| Aspect | Detail |
|--------|--------|
| Protocol Support | Limited connectors for BMS/Modbus/SNMP |
| Visual Design | No visual flow designer (code-only) |
| Real-time Only | No native batch processing |
| Custom Connectors | May need to build custom connectors |

**Best For:** Kafka-centric environments, limited source diversity

---

### 3.4 Stack C: Pulsar + Functions

**Architecture:**
```
Sources → Pulsar IO (ingest) → Pulsar → Pulsar Functions (process) → Sinks
```

**Pros:**
| Aspect | Detail |
|--------|--------|
| Unified | Messaging + compute in one system |
| Multi-tenancy | Built-in tenant isolation |
| Tiered Storage | Offload old data to S3/GCS |
| Geo-replication | Built-in for multi-site |

**Cons:**
| Aspect | Detail |
|--------|--------|
| Maturity | Less mature than Kafka ecosystem |
| Community | Smaller community than Kafka |
| Connector Ecosystem | Fewer connectors than Kafka Connect |
| Operational | Pulsar cluster management is complex |

**Best For:** Multi-site DCIM, need for tiered storage

---

### 3.5 Stack D: Camel + Kafka

**Architecture:**
```
Sources → Camel (integration) → Kafka → Camel (process) → Sinks
```

**Pros:**
| Aspect | Detail |
|--------|--------|
| Integration Focus | 300+ components for integration |
| Protocol Support | Excellent for enterprise protocols |
| Flexibility | Java/DSL-based, very flexible |
| Enterprise | Red Hat support available |

**Cons:**
| Aspect | Detail |
|--------|--------|
| Complexity | Camel DSL has steep learning curve |
| Visual Design | No native visual designer |
| Performance | Higher overhead than native Kafka |
| Java Dependency | Requires Java expertise |

**Best For:** Enterprise environments with diverse protocols

---

### 3.6 Stack E: Custom Python/Go + Kafka

**Architecture:**
```
Sources → Custom Ingest (Python/Go) → Kafka → Custom Process → Sinks
```

**Pros:**
| Aspect | Detail |
|--------|--------|
| Simplicity | Minimal components |
| Control | Full control over processing |
| Lightweight | Low resource usage |
| Python Ecosystem | Rich libraries for data processing |

**Cons:**
| Aspect | Detail |
|--------|--------|
| Development Effort | Must build everything custom |
| Maintenance | Custom code requires ongoing maintenance |
| Scalability | Must implement scaling ourselves |
| Protocol Support | Must implement each protocol handler |

**Best For:** Small-scale, specific use cases, rapid prototyping

---

### 3.7 Stack Comparison Matrix

| Feature | Stack A | Stack B | Stack C | Stack D | Stack E |
|---------|---------|---------|---------|---------|---------|
| **Visual Design** | ✅ NiFi | ❌ | ❌ | ❌ | ❌ |
| **Protocol Support** | ✅ 100+ | ⚠️ Limited | ⚠️ Limited | ✅ 300+ | ❌ Custom |
| **Real-time** | ✅ Flink | ✅ Streams | ✅ Functions | ⚠️ Limited | ⚠️ Custom |
| **Batch** | ✅ NiFi | ❌ | ⚠️ Pulsar IO | ✅ Camel | ⚠️ Custom |
| **Scalability** | ✅ High | ✅ High | ✅ High | ✅ High | ⚠️ Medium |
| **Operational** | ⚠️ Complex | ✅ Simple | ⚠️ Complex | ⚠️ Complex | ✅ Simple |
| **Maturity** | ✅ High | ✅ High | ⚠️ Medium | ✅ High | ⚠️ Varies |
| **DCIM Fit** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |

---

## 4. Deployment Pattern Comparison

### 4.1 Centralized Gateway

```
┌─────────────────────────────────────────────────────────────┐
│                    Central DI&I Gateway                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │ NiFi    │  │ Kafka   │  │ Flink   │  │ Schema  │      │
│  │ Cluster │  │ Cluster │  │ Cluster │  │ Registry│      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │
└─────────────────────────────────────────────────────────────┘
         ↑              ↑              ↑              ↑
    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
    │ Site A  │    │ Site B  │    │ Site C  │    │ Cloud   │
    │Sources  │    │Sources  │    │Sources  │    │Sources  │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Management | Single cluster to manage |
| Consistency | Uniform processing across all sources |
| Cost | Shared infrastructure |
| Expertise | Team focuses on one deployment |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Latency | Network hop for remote sites |
| Single Point of Failure | Gateway failure affects all sites |
| Bandwidth | All data flows to central location |
| Scalability | Central cluster must handle all load |

**Best For:** Small to medium deployments (< 5 sites), low-latency requirements

---

### 4.2 Distributed Edge

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Site A     │    │  Site B     │    │  Site C     │
│  ┌───────┐  │    │  ┌───────┐  │    │  ┌───────┐  │
│  │ NiFi  │──┼───→│  │ NiFi  │──┼───→│  │ NiFi  │──┼──→ Central
│  │ Kafka │  │    │  │ Kafka │  │    │  │ Kafka │  │    Kafka
│  └───────┘  │    │  └───────┘  │    │  └───────┘  │
└─────────────┘    └─────────────┘    └─────────────┘
```

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Latency | Local processing, low latency |
| Resilience | Site failure doesn't affect others |
| Bandwidth | Only processed data flows to central |
| Scalability | Each site scales independently |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Management | Multiple clusters to manage |
| Consistency | Risk of inconsistent processing |
| Cost | More infrastructure |
| Expertise | Team must manage distributed systems |

**Best For:** Large deployments (> 10 sites), high-latency networks, regulatory requirements

---

### 4.3 Hybrid (Recommended for DCIM)

```
┌─────────────────────────────────────────────────────────────┐
│                    Central DI&I Gateway                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │
│  │ NiFi    │  │ Kafka   │  │ Flink   │  │ Schema  │      │
│  │ Cluster │  │ Cluster │  │ Cluster │  │ Registry│      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │
└─────────────────────────────────────────────────────────────┘
         ↑              ↑              ↑              ↑
    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐    ┌────┴────┐
    │ Edge    │    │ Edge    │    │ Direct  │    │ Direct  │
    │ NiFi    │    │ NiFi    │    │ Connect │    │ Connect │
    │ (Site A)│    │ (Site B)│    │ (Cloud) │    │ (API)   │
    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

**Characteristics:**
- Edge NiFi for high-volume or protocol-specific sites
- Direct connection for cloud/API sources
- Central gateway for processing and routing
- Best of both worlds

**Pros:**
| Aspect | Benefit |
|--------|---------|
| Flexibility | Right approach per source |
| Latency | Edge processing for time-critical |
| Bandwidth | Pre-processing at edge reduces central load |
| Management | Centralized for most, distributed where needed |

**Cons:**
| Aspect | Drawback |
|--------|----------|
| Complexity | Multiple deployment patterns |
| Consistency | Need to ensure uniform processing |
| Monitoring | Must monitor both edge and central |

**Best For:** Multi-site DCIM with mixed requirements

---

### 4.4 Deployment Pattern Matrix

| Pattern | Sites | Latency | Bandwidth | Management | Cost |
|---------|-------|---------|-----------|------------|------|
| Centralized | < 5 | Higher | High | Simple | Low |
| Distributed | > 10 | Low | Low | Complex | High |
| Hybrid | 5-10 | Mixed | Medium | Medium | Medium |

---

## 5. Processing Mode Analysis

### 5.1 Processing Mode Comparison

| Mode | Latency | Use Case | DCIM Sources | SLA |
|------|---------|----------|--------------|-----|
| **Real-time** | < 1s | Critical alerts, security events | P1/P2 alarms, access control | S1/S2 |
| **Near-RT** | 1-30s | Operational metrics, status changes | NMS, server monitoring | S2/S3 |
| **Micro-batch** | 1-60s | Aggregated metrics | Performance counters | S3 |
| **Batch** | 1-60 min | Historical sync, bulk import | Nightly reconciliation | S3/S4 |
| **Async** | > 1h | Report generation, analytics | Capacity planning, forecasting | S4 |

### 5.2 Technology Mapping

| Mode | Primary Tool | Secondary Tool | Notes |
|------|--------------|----------------|-------|
| Real-time | Apache Flink | Kafka Streams | Stateful processing, windowing |
| Near-RT | Kafka Consumers | NiFi (NRT mode) | Simple transformations |
| Micro-batch | Spark Streaming | Kafka + Timer | Aggregation windows |
| Batch | NiFi (scheduled) | Airflow | Scheduled flows |
| Async | Python/Go jobs | Cron + Scripts | Background processing |

### 5.3 DCIM Processing Requirements

| Priority | Event Type | Required Mode | Tool | SLA |
|----------|------------|---------------|------|-----|
| P1 | UPS failure, fire alarm | Real-time (< 1s) | Flink | Immediate |
| P1 | Security breach | Real-time (< 1s) | Flink | Immediate |
| P2 | Network down | Near-RT (< 30s) | Kafka Consumer | < 1 min |
| P2 | Server offline | Near-RT (< 30s) | Kafka Consumer | < 1 min |
| P3 | Performance degradation | Micro-batch (< 60s) | Kafka + Timer | < 5 min |
| P3 | Capacity threshold | Batch (5 min) | NiFi | < 15 min |
| P4 | Historical sync | Batch (1 hour) | NiFi | Next cycle |
| P4 | Reconciliation | Batch (daily) | NiFi | Nightly |

---

## 6. DCIM Source Systems Matrix

### 6.1 Source System Characteristics

| Source | Protocol | Volume | Latency Need | Data Quality Need | Best Pattern |
|--------|----------|--------|--------------|-------------------|--------------|
| **BMS** | Modbus/BACnet | Medium | NRT (5-30s) | High (critical) | Hybrid |
| **EPMS** | Modbus/SNMP | Medium | Real-time (< 1s) | Critical | Centralized |
| **NMS** | SNMP v3 | High | NRT (1-10s) | High | Hybrid |
| **Server Monitor** | Agent/API | High | NRT (5-15s) | Medium | Centralized |
| **Storage** | API/SNMP | Medium | NRT (10-30s) | Medium | Centralized |
| **Virtualization** | API | Medium | NRT (30s-5min) | Low | Centralized |
| **Cloud** | API | High | NRT (1-5min) | Low | Centralized |
| **Access Control** | API/Syslog | Low | Real-time (< 1s) | Critical | Centralized |
| **Surveillance** | RTSP/ONVIF | Very High | NRT (1-5s) | Medium | Hybrid |
| **ITSM** | REST API | Low | Batch (5-60min) | High | Centralized |
| **ERP** | REST/SFTP | Low | Batch (1-24h) | Critical | Centralized |
| **DMS** | REST/SFTP | Low | Batch (1-24h) | High | Centralized |

### 6.2 Protocol Complexity

| Protocol | Complexity | NiFi Support | Custom Code Needed |
|----------|------------|--------------|-------------------|
| REST API | Low | ✅ InvokeHTTP | No |
| SNMP v2c/v3 | Medium | ✅ GetSNMP | No |
| Modbus TCP | Medium | ✅ Custom Processor | Minimal |
| BACnet | High | ⚠️ Limited | Yes (adapter) |
| MQTT | Low | ✅ ConsumeMQTT | No |
| Syslog | Low | ✅ ListenSyslog | No |
| SSH | Medium | ✅ ExecuteStreamCommand | No |
| JDBC/ODBC | Low | ✅ SelectSQL / ExecuteSQL | No |
| SFTP/FTPS | Low | ✅ FetchSFTP | No |
| RTSP/ONVIF | High | ❌ | Yes (adapter) |

### 6.3 Enrichment Requirements

| Source | CI Lookup | Location | Priority | Financial |
|--------|-----------|----------|----------|-----------|
| BMS | ✅ Required | ✅ Required | ✅ Required | ❌ No |
| EPMS | ✅ Required | ✅ Required | ✅ Required | ❌ No |
| NMS | ✅ Required | ⚠️ Optional | ✅ Required | ❌ No |
| Server | ✅ Required | ✅ Required | ✅ Required | ⚠️ Optional |
| Access Control | ✅ Required | ✅ Required | ✅ Required | ❌ No |
| ITSM | ✅ Required | ❌ No | ✅ Required | ⚠️ Optional |
| ERP | ❌ No | ❌ No | ❌ No | ✅ Required |

---

## 7. Recommendation Matrix

### 7.1 Decision Framework

| Factor | Weight | Option A | Option B | Option C |
|--------|--------|----------|----------|----------|
| Source Diversity | 25% | NiFi+Kafka+Flink | Kafka-native | Pulsar |
| SLA Compliance | 25% | NiFi+Kafka+Flink | Kafka-native | NiFi+Kafka |
| Operational Simplicity | 20% | Kafka-native | Custom | NiFi+Kafka+Flink |
| Scalability | 15% | NiFi+Kafka+Flink | Kafka-native | Pulsar |
| Team Skills | 15% | (Based on team) | (Based on team) | (Based on team) |

### 7.2 Final Recommendation for DCIM

**Primary: Hybrid Architecture + Stack A (NiFi + Kafka + Flink)**

| Aspect | Recommendation |
|--------|----------------|
| **Architecture** | Hybrid (centralized gateway + edge where needed) |
| **Ingestion** | Apache NiFi (visual design, protocol support) |
| **Message Broker** | Apache Kafka (event backbone, 3 brokers, KRaft) |
| **Real-time Processing** | Apache Flink (P1/P2 alerts, stateful processing) |
| **Near-RT Processing** | Kafka Consumers (P2/P3 metrics) |
| **Batch Processing** | NiFi scheduled flows (P3/P4 reconciliation) |
| **Schema Management** | Confluent Schema Registry (Avro) |
| **Data Quality** | Centralized validation + enrichment in NiFi |

**Rationale:**
1. **Source Diversity:** NiFi's 100+ processors handle BMS, NMS, server, cloud protocols
2. **SLA Compliance:** Flink for real-time, Kafka consumers for near-RT, NiFi for batch
3. **Data Quality:** Centralized validation/enrichment ensures consistency
4. **Operational:** Visual NiFi flows easier to debug than code-only
5. **Maturity:** All components are Apache top-level projects

### 7.3 Alternative Recommendations

| Scenario | Recommended Stack | Rationale |
|----------|-------------------|-----------|
| Small DCIM (< 1000 devices) | Stack E (Custom Python/Go) | Lower complexity, sufficient for scale |
| Kafka-centric org | Stack B (Kafka-native) | Leverage existing expertise |
| Multi-site (> 10 sites) | Stack C (Pulsar) | Built-in geo-replication, tiered storage |
| Enterprise with Red Hat | Stack D (Camel+Kafka) | Enterprise support available |

---

## 8. Gap Comparison Template

### Gap: Architecture Pattern

| Aspect | Reference Design | Actual Implementation | Gap | Priority |
|--------|-----------------|----------------------|-----|----------|
| Pattern | Hybrid | [aktual] | [match/mismatch] | P1-P4 |
| Processing Paths | 3 (real-time, near-RT, batch) | [aktual] | [match/mismatch] | P1-P4 |
| Centralized Gateway | Yes | [aktual] | [match/mismatch] | P1-P4 |

**Decision:** [adopt spec / keep actual / hybrid]
**Rationale:** [why]
**Action items:** [what to do]

---

### Gap: Technology Stack

| Aspect | Reference Design | Actual Implementation | Gap | Priority |
|--------|-----------------|----------------------|-----|----------|
| Ingestion Tool | NiFi | [aktual] | [match/mismatch] | P1-P4 |
| Message Broker | Kafka | [aktual] | [match/mismatch] | P1-P4 |
| Stream Processing | Flink | [aktual] | [match/mismatch] | P1-P4 |
| Schema Registry | Confluent | [aktual] | [match/mismatch] | P2-P4 |

**Decision:** [adopt spec / keep actual / hybrid]
**Rationale:** [why]
**Action items:** [what to do]

---

### Gap: Deployment Pattern

| Aspect | Reference Design | Actual Implementation | Gap | Priority |
|--------|-----------------|----------------------|-----|----------|
| Pattern | Hybrid (central + edge) | [aktual] | [match/mismatch] | P1-P4 |
| Edge Deployment | Where needed | [aktual] | [match/mismatch] | P2-P4 |
| Multi-site | Supported | [aktual] | [match/mismatch] | P2-P4 |

**Decision:** [adopt spec / keep actual / hybrid]
**Rationale:** [why]
**Action items:** [what to do]

---

### Gap: Processing Modes

| Aspect | Reference Design | Actual Implementation | Gap | Priority |
|--------|-----------------|----------------------|-----|----------|
| Real-time (< 1s) | Flink for P1/P2 | [aktual] | [match/mismatch] | P1-P4 |
| Near-RT (1-30s) | Kafka Consumers | [aktual] | [match/mismatch] | P1-P4 |
| Batch (min-hrs) | NiFi scheduled | [aktual] | [match/mismatch] | P1-P4 |

**Decision:** [adopt spec / keep actual / hybrid]
**Rationale:** [why]
**Action items:** [what to do]

---

### Gap: Protocol Support

| Protocol | Reference Design | Actual Implementation | Gap | Priority |
|----------|-----------------|----------------------|-----|----------|
| REST API | ✅ NiFi InvokeHTTP | [aktual] | [match/mismatch] | P1-P4 |
| SNMP v3 | ✅ NiFi GetSNMP | [aktual] | [match/mismatch] | P1-P4 |
| Modbus TCP | ✅ NiFi Custom | [aktual] | [match/mismatch] | P2-P4 |
| MQTT | ✅ NiFi ConsumeMQTT | [aktual] | [match/mismatch] | P2-P4 |
| BACnet | ⚠️ Adapter needed | [aktual] | [match/mismatch] | P2-P4 |

**Decision:** [adopt spec / keep actual / hybrid]
**Rationale:** [why]
**Action items:** [what to do]

---

## References

- [[block2-data-ingestion-integration]] — Reference design spec untuk DI&I
- [[data-integration-comparison]] — Perbandingan tool integrasi data
- [[data-pipeline-comparison]] — Perbandingan pipeline solutions
- [[kafka]] — Message broker architecture
- [[nifi]] — Data flow orchestration
- [[dcim-core-platform]] — Platform overview
