![An abstract, professional illustration of data flow and integration
pipelines connecting various data sources to a central repository,
symbolizing the Data Ingestion & Integration
Layer.](media/image1.jpg){width="8.0in" height="2.2222222222222223in"}

Technical Requirements - Data Ingestion & Integration Layer

1\. Pendahuluan

Dokumen ini menetapkan persyaratan teknis untuk komponen Data Ingestion
& Integration Layer dalam Proyek Manajemen Infrastruktur Pusat Data
(DCIM). Layer ini bertanggung jawab untuk mengumpulkan, memproses,
menormalkan, dan mengirimkan data Configuration Item (CI), monitoring,
dan operasional dari berbagai sumber ke Configuration Management
Database (CMDB) dan komponen DCIM inti lainnya.

1.1. Konteks Proyek
===================

  Field               Description
  ------------------- ----------------------------------------------------------------
  Nama Proyek         Data Center Infrastructure Management (DCIM) Core Platform
  Komponen            Data Ingestion & Integration Layer
  Versi Dokumen       1.0
  Tanggal Pembuatan   20 Jan 2026
  Disiapkan Oleh      [[Imam Syauqi Achmad]{.underline}](mailto:isyauqi93@gmail.com)

2\. Kebutuhan Fungsional

The Data Ingestion & Integration Layer must fulfill the following core
functions:

2.1. Data Source Connectivity
=============================

-   **Requirement 2.1.1 (Protocol Support):**

> Harus support berbagai macam protokol agar lebih fleksible saat ada
> penambahan protokol baru:

-   REST API - Polling/Webhook - Apache Nifi, Kafka Connect HTTP

-   SNMP - Polling device - Telegraf, snmp\_exporter

-   SSH - Remote Command / Script - Ansible, Custom Python script

-   JDBC/ODBC - Database polling - Kafka connect JDBC

-   Syslog - Real-time log - Filebeat / Logstash

-   SFTP/FTPS - File-based ingestion - Nifi, Filebeat

```{=html}
<!-- -->
```
-   **Requirement 2.1.2 (Connectors):**

    -   REST API + NiFi untuk NMS (Zabbix/Prometheus/Grafana)

    -   SNMP + Telegraf untuk PDU, UPS, atau sensor lingkungan

    -   REST API untuk VMWare / Hyper-V / Proxmox

    -   JDBC / REST untuk Legacy asset management

2.2. Data Transformation & Normalization
========================================

-   **Requirement 2.2.1 (Mapping):**

    -   Gunakan **DCIM Common Data Model (CDM)**

    -   CI Type - Mandatory Fields:

        -   Server - hostname, serial, rack, power\_state

        -   Network - hostname, ip, model

        -   PDU - outlet, load, capacity

        -   Sensor - metric, value, unit

    -   Tentukan **CDM schema CMDB**

    -   Buat mapping table:\
        > source.hostname → cmdb.ci\_name

> source.ip → cmdb.primary\_ip
>
> source.rack → cmdb.location.rack

-   Tools:

    -   Apache NiFi (Record Processor)

    -   StreamSets

```{=html}
<!-- -->
```
-   **Requirement 2.2.2 (Data Cleansing):** Must include capabilities
    > for data cleansing, error handling (e.g., missing values,
    > incorrect format), and standardization (e.g., unit conversion,
    > case transformation) before insertion into the CMDB.

    -   Validasi schema

  **Jenis Validasi**   **Contoh DCIM**
  -------------------- ----------------------------
  Mandatory field      ci\_id, hostname, location
  Data type            power\_kw harus numeric
  Range                suhu 0--60°C
  Format               IP address, MAC
  Referential          rack\_id harus ada

-   Tools:

    -   Apache NiFi (ValidateRecord, ValidateXml, ValidateJson)

    -   Python (pydantic, jsonschema)

```{=html}
<!-- -->
```
-   Error Handling

    -   Default value untuk missing field

    -   Konversi unit (W → kW, °C → Kelvin jika perlu)

  **Error**        **Contoh**
  ---------------- -----------------------
  Missing value    rack\_id kosong
  Invalid format   IP salah
  Mapping gagal    field tidak dikenal
  Lookup gagal     owner tidak ditemukan

-   Cara menangani:

    -   Tag error

    -   Kirim ke DLQ

    -   Alert ke ops

-   Fungsi - Tools

    -   DLQ - Kafka topic

    -   Error store - PostgreSQL

    -   Alert - Alertmanager (Prometheus)

```{=html}
<!-- -->
```
-   Normalisasi string

    -   Unit Conversion

  **Source**   **DCIM Standard**
  ------------ -----------------------
  12000 W      12 kW
  35 °C        308.15 K (jika perlu)
  80 %         0.8

-   Naming Convention

  **Source**        **Standard**
  ----------------- --------------
  Rack-01           RACK\_01
  srv-01.dc.local   SRV-01

-   Boolean & Status

  **Source**   **Standard**
  ------------ --------------
  yes/no       true/false
  UP/DOWN      1 / 0

-   Tools:

    -   NiFi (Update Record, ReplaceText, ExecuteScript)

    -   Flink (Map & Filler)

```{=html}
<!-- -->
```
-   **Requirement 2.2.3 (Enrichment):** Must be able to enrich ingested
    > data with contextual information (e.g., location, owner from Asset
    > Repository) using lookup tables or external services.

    -   Enrichment tidak boleh overwrite source data.

    -   Reference / Lookup Enrichment, menambahkan atribut dari master
        > data.

  **Field Baru**   **Diambil Dari**
  ---------------- ------------------
  location.site    Site master
  rack.row         Rack DB
  owner            Asset Repository
  business\_unit   CMDB master

-   Gunakan **lookup key** (hostname, asset\_id, serial number).

-   Join ke tabel referensi.

-   Tools:

    -   Apache NiFi (LookupRecord)

    -   Redis (Cache lookup)

    -   PostgreSQL (Reference DB)

    -   REST API (External CMDB)

-   Contoh:

    -   Raw:\
        > {\
        > \"hostname\": \"srv-01\",\
        > \"rack\_id\": \"R12\"\
        > }

    -   Setelah enrichment:\
        > {\
        > \"hostname\": \"srv-01\",\
        > \"rack\_id\": \"R12\",\
        > \"site\": \"DC-JKT-01\",\
        > \"row\": \"ROW-B\",\
        > \"owner\": \"IT-OPS\"\
        > }

```{=html}
<!-- -->
```
-   Topology & Relationship Enrichment, membangun relasi antar CI.

  **CI**   **Relasi**
  -------- -----------------
  Server   Mounted in Rack
  Rack     Located in Room
  Server   Powered by PDU
  VM       Runs on Host

-   Identifikasi foreign key

-   Bentuk relationship object

-   Simpan ke CMDB

-   Tools:

    -   NiFi (ExecuteScript)

    -   Python grahp logic

    -   CMDB Relationship API

-   Contoh:\
    > {

> \"ci\_id\": \"srv-01\",
>
> \"relationship\": {
>
> \"type\": \"mounted\_in\",
>
> \"target\": \"rack-R12\"
>
> }
>
> }

-   Contextual Enrichment (Environment & Business), menambahkan makna
    > operasional dan bisnis.

  **Atribut**   **Sumber**
  ------------- ---------------
  environment   Dev / Prod
  criticality   High / Medium
  SLA           SLA DB
  compliance    Policy engine

-   Rule-based mapping

-   Lookup ke CMDB atau policy service

-   Tools:

    -   NiFi Rules

    -   Python decision logic

    -   Config YAML

```{=html}
<!-- -->
```
-   Time-Based Enrichment, menambah konteks waktu

    -   Contoh:

        -   Shift Kerja

        -   Jam Operasional

        -   Maintenance Window

    -   Contoh:

> {
>
> \"event\_time\": \"2026-01-21T02:00:00Z\",
>
> \"maintenance\_window\": true
>
> }

-   Geo & Location Enrichment

    -   Mendukung:

        -   Heat map

        -   Capacity planning

        -   Disaster Impact

  **Field**   **Nilai**
  ----------- -----------
  latitude    -6.2
  longitude   106.8
  region      APAC

-   Error Handling

    -   Enrichment gagal data tidak di drop

    -   Field diberi status enrichment\_status

    -   Contoh:

> {
>
> \"hostname\": \"srv-99\",
>
> \"owner\": null,
>
> \"enrichment\_status\": \"PARTIAL\"
>
> }

-   Strategi:

  **Kasus**        **Tindakan**
  ---------------- -------------------
  Lookup gagal     Cache retry
  API down         Skip + flag
  Data tidak ada   Default / UNKNOWN

-   Caching Strategy

    -   Lookup bisa ribuan per detik

    -   Jangan Query DB terus

    -   Tools:

        -   Redis - Lookup cepat

        -   In-memory - Local microservice

        -   TTL - Auto refresh

2.3. Data Flow Management
=========================

-   **Requirement 2.3.1 (Batch and Streaming):**

    -   #### Streaming → Kafka topic

    -   #### Batch → Scheduler + Kafka

    -   #### Tools:

        -   #### Streaming -\> Kafka + Flink

        -   #### Batch -\> NiFi Scheduler / Airflow

    -   Batch Processing

        -   Sumber Data Batch

  **Source**         **Metode**
  ------------------ ----------------
  Asset DB           JDBC polling
  VMware             Scheduled REST
  File inventory     SFTP
  Discovery script   SSH

-   Scheduling

  **Tool**         **Fungsi**
  ---------------- --------------------
  Apache NiFi      Native scheduler
  Apache Airflow   Complex dependency
  Cron + Script    Simple batch

-   Batch Optimization

  **Teknik**         **Manfaat**
  ------------------ ---------------
  Incremental load   Kurangi beban
  Checkpoint         Resume aman
  Parallel batch     Throughput

-   Streaming Processing

    -   Sumber Data Streaming

  **Source**   **Metode**
  ------------ ------------
  Syslog       Filebeat
  SNMP Trap    Telegraf
  Event API    Webhook
  Sensor       MQTT

-   Failure & Retry Strategy

  **Mode**          **Penanganan**
  ----------------- --------------------
  Batch gagal       Retry + checkpoint
  Streaming gagal   Replay Kafka
  Partial batch     Resume

-   Performance Target

  **Mode**    **Target**
  ----------- ------------------
  Batch       5k+ records/sec
  Streaming   \<500 ms latency
  Kafka       100k msg/sec

-   Monitoring Batch & Streaming

  **Metric**     **Mode**
  -------------- -------------------
  Throughput     Batch & Streaming
  Latency        Streaming
  Lag            Streaming
  Job duration   Batch

-   Tools:

    -   Prometheus

    -   Grafana

    -   Kafka Exporter

```{=html}
<!-- -->
```
-   **Requirement 2.3.2 (Error Handling):**

    -   Cara menangani:

        -   Record gagal → kirim ke Dead Letter Queue (DLQ)

        -   Jangan drop data

    -   DLQ berbasis Kafka topic / DB table

    -   Metadata lengkap

    -   Tools:

        -   Kafka DLQ topic

        -   PostgreSQL (error table)

        -   Alert via Alertmanager (Prometheus)

-   **Requirement 2.3.3 (Data Lineage):** Must track and log the source,
    > timestamp, and transformation steps for every ingested record for
    > auditing and troubleshooting purposes.

    -   Simpan metadata:

        -   Source

        -   Timestamp

        -   Pipeline ID

        -   Transformation version

    -   Tools:

        -   NiFi Provenance

        -   OpenLineage

        -   Custom Metadata DB

3\. Kebutuhan Non-Fungsional

3.1. Performance & Scalability
==============================

-   **Requirement 3.1.1 (Throughput):** Must be capable of processing
    > and transforming a sustained load of 5,000 data records per second
    > during peak hours.

    -   Sistem mampu memproses **≥ 5k msg/s end-to-end**

    -   Sudah termasuk:

        -   Ingest

        -   Transform

        -   Enrich

        -   Deliver

    -   Decoupling dengan Message Broker

        -   Gunakan Kafka sebagai buffe**r**

        -   Producer ≠ Consumer

            -   **Producer → Kafka → Consumer**

    -   Parallel Processing

        -   Partition Kafka

        -   Consumer group

  **Komponen**   **Konfigurasi**
  -------------- ------------------
  Kafka          ≥ 6 partition
  Consumer       ≥ 3 instance
  NiFi           Concurrent tasks

-   Stateless Processing

    -   Jangan simpan state di memory lokal

    -   State → external store

-   Tools:

    -   Apache Kafka

    -   Apache NiFi / Flink

    -   Kubernetes HPA

```{=html}
<!-- -->
```
-   **Kebutuhan 3.1.2 (Latency):** Latency for critical streaming data
    > pipelines (e.g., alerts) must be consistently under 500
    > milliseconds from source detection to target delivery.

    -   Streaming-first Design

        -   Hindari batch untuk data kritikal

        -   Event-driven ingestion

    -   Lightweight Processing

        -   Rule sederhana

        -   Hindari lookup berlebihan

        -   Gunakan cache

    -   Async & Non-blocking I/O

        -   REST async

        -   Kafka async producer

    -   Tools:

        -   Kafka (low-latency config)

        -   Apache Flink

        -   Redis cache

    -   Contoh Timeline:

        -   Sensor Event → 20ms

        -   Kafka → 30ms

        -   Processing → 100ms

        -   CMDB API → 200ms

        -   TOTAL ≈ 350ms

-   **Kebutuhan 3.1.3 (Scaling):** The layer must be designed as a
    > distributed system that can scale horizontally to handle increased
    > data volume and velocity by adding resources.

    -   Microservices Architeture

        -   Ingestor

        -   Processor

        -   Enricher

        -   Sink

    -   Containerization & Orchestration

        -   Docker

        -   Kubernetes

    -   Auto Scaling

        -   Scale Berdasarkan:

            -   CPU

            -   Kafka lag

            -   Throughput

    -   Tools:

        -   Kubernetes HPA

        -   Kafka Exporter

        -   Prometheus

3.2. Reliability & Availability
===============================

-   **Requirement 3.2.1 (HA):** The ingestion pipeline must be highly
    > available with no single point of failure (SPOF) and provide
    > automatic failover capabilities.

    -   

  **Komponen**   **Solusi**
  -------------- ---------------
  Kafka          3+ broker
  NiFi           Cluster mode
  DB             PostgreSQL HA

-   **Requirement 3.2.2 (Idempotency):** The ingestion process must be
    > idempotent to prevent duplicate data insertion or processing when
    > re-running a job or recovering from a failure.

    -   Cara menangani:

        -   Gunakan **unique key (CI\_ID)**

        -   Upsert, bukan insert

    -   Tools:

        -   CMDB API idempotent endpoint

        -   Kafka message key

3.3. Security
=============

-   **Requirement 3.3.1 (Credential Management):** Must securely store
    > and manage credentials (e.g., API keys, SSH keys, passwords)
    > required for connecting to source systems, preferably via
    > integration with an enterprise vault/key management system.

    -   Jangan simpan password di config file

    -   Tools:

        -   Hashicorp Vault

        -   Kubernetes Secrets

        -   Ansible Vault

-   **Requirement 3.3.2 (Data in Transit):** All data transfer between
    > the ingestion layer and external sources/targets must utilize
    > encrypted channels (e.g., TLS 1.2+).

    -   TLS di semua channel

    -   Tools:

        -   HTTPS

        -   Kafka SSL

        -   mTLS (internal service)

4\. Spesifikasi Teknis

4.1. Architecture
=================

Data Ingestion & Integration Layer harus dibangun menggunakan
**arsitektur modular berbasis microservices**, dengan tujuan:

-   Memisahkan tanggung jawab tiap komponen (decoupled)

-   Mudah diskalakan secara horizontal

-   Fault-tolerant dan mudah diobservasi

-   Mendukung batch dan streaming secara bersamaan

4.2. Technology Stack
=====================

  Category                           Requirement                                                               Preferred Technology/Platform                               Notes
  ---------------------------------- ------------------------------------------------------------------------- ----------------------------------------------------------- ------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Ingestion Framework                Mendukung pemrosesan batch dan streaming                                  Apache Kafka, Kafka Connect, Filebeat                       Kafka digunakan sebagai backbone event-driven untuk throughput tinggi dan buffering lonjakan data. Filebeat digunakan untuk ingestion log dan syslog secara real-time.
  Processing Engine                  Transformasi, normalisasi, dan pemetaan data ke Common Data Model (CDM)   Apache NiFi, Apache Flink (opsional), microservice Python   NiFi digunakan untuk visual flow, data provenance, dan audit. Flink digunakan untuk kebutuhan streaming dengan latency sangat rendah
  Message Broker                     Penyangga data dan decoupling antar komponen                              Apache Kafka                                                Menyediakan mekanisme replay, partitioning, dan fault tolerance untuk ingestion DCIM.
  Database/Storage                   Penyimpanan metadata pipeline, error queue, dan audit data                PostgreSQL, MongoDB                                         PostgreSQL untuk data terstruktur (DLQ, metadata). MongoDB opsional untuk data semi-terstruktur.
  Cache Enrichment                   Lookup data referensi berfrekuensi tinggi                                 Redis                                                       Digunakan untuk mengurangi latency enrichment dan beban ke database utama.
  Containerization                   For deployment and scaling                                                Docker/Kubernetes                                           Mendukung skalabilitas horizontal, high availability, dan rolling update tanpa downtime.
  Monitoring & Metrics               Monitoring performa ingestion dan pipeline                                Prometheus, Grafana                                         Digunakan untuk memonitor throughput, latency, error rate, dan Kafka lag.
  Logging Terpusat                   Logging terpusat dan audit trail                                          ELK Stack (Filebeat, Logstash, Elasticsearch, Kibana)       Digunakan untuk troubleshooting, audit, dan integrasi dengan sistem logging DCIM.
  Security & Credential Management   Manajemen kredensial dan secret                                           Kubernetes Secrets, HashiCorp Vault (opsional)              Kredensial tidak disimpan di konfigurasi statis atau source code.
  CI/CD (Opsional)                   Otomatisasi deployment dan konfigurasi                                    GitLab CI / GitHub Actions                                  Mendukung versioning pipeline dan deployment yang konsisten.

4.3. Monitoring and Logging
===========================

-   **Requirement 4.3.1:** Must expose ingestion metrics (e.g.,
    > throughput, success/fail rate, latency per pipeline) via standard
    > protocols (e.g., Prometheus/JMX).

    -   Metric yang wajib disediakan

  **Metric**             **Deskripsi**
  ---------------------- ------------------------
  Throughput             Jumlah record / detik
  Success rate           Data berhasil diproses
  Failure rate           Data gagal
  Latency per pipeline   End-to-end latency
  Kafka lag              Backlog processing

-   Tools Monitoring:

    -   Prometheus

    -   Grafana

    -   JMX exporter

    -   Kafka exporter

```{=html}
<!-- -->
```
-   **Requirement 4.3.2:** Must log all processing steps, errors, and
    > data flow events centrally and be integrated with the DCIM logging
    > system.

    -   Jenis Log

  **Log Type**     **Isi**
  ---------------- ------------------------
  Ingestion log    Data masuk
  Processing log   Transform & enrichment
  Error log        Validation & DLQ
  Audit log        Lineage & trace

-   Tools Logging

    -   Filebeat

    -   Logstash

    -   Elasticsearch

    -   Kibana

5\. Integration Targets

Fungsi utama lapisan ini adalah untuk memasok data ke komponen inti DCIM
berikutnya:

  Target Component                           Data Type                                         Communication Protocol                          Target CMDB Section
  ------------------------------------------ ------------------------------------------------- ----------------------------------------------- -------------------------------------
  Configuration Management Database (CMDB)   CI data, relationships, attributes                REST API CMDB, Database Write (Upsert)          Repository CI dan Relationship CMDB
  Monitoring System                          Data sensor real-time, event operasional, alert   Apache Kafka (Message Queue), REST API          Dashboard Operasional / NOC View
  Analytics & AI Engine                      Historical data for trend analysis                Apache Kafka, Database Write                    Data Lake/Warehouse
  Centralized Logging                        Log ingestion, error, audit, dan data lineage     ELK Stack (Filebeat, Logstash, Elasticsearch)   Centralized Logging DCIM
  Reporting System & Dashboard               Data ringkasan operasional dan performa           REST API / Query Database                       Dashboard Manajemen & Operasional

Appendix: Change Log

  Version   Date          Author                                                                   Description of Change
  --------- ------------- ------------------------------------------------------------------------ -----------------------------------------------------------------------------
  1.0       20 Jan 2026   [[shuffahaqgzz\@gmail.com]{.underline}](mailto:shuffahaqgzz@gmail.com)   Initial draft of Data Ingestion & Integration Layer Technical Requirements.
  2.0       21 Jan 2026   [[Imam Syauqi Achmad]{.underline}](mailto:isyauqi93@gmail.com)           
