![A stylized digital illustration of various data streams merging into a
central, secure processing unit, representing data ingestion and
integration in a data center
environment.](media/image1.jpg){width="8.0in"
height="2.2222222222222223in"}

Use Case Analysis: Data Ingestion & Integration Layer

Introduction
============

Dokumen ini menyediakan analisis use case mendetail untuk komponen
Lapisan Data Ingestion & Integration dalam Proyek Data Center
Infrastructure Management (DCIM). Lapisan ini sangat krusial untuk
mengumpulkan, mentransformasi, dan mengonsolidasikan beragam data dari
berbagai sumber di seluruh infrastruktur pusat data untuk mendukung
pemantauan, analitik, dan otomatisasi yang komprehensif.

Component Overview
==================

Lapisan Data Ingestion & Integration berfungsi sebagai mekanisme utama
untuk mengabstraksi kompleksitas sumber data dan memastikan aliran data
yang terpadu dan berkualitas tinggi bagi komponen DCIM selanjutnya
(misalnya, Configuration Management Database, Analytics & AI Engine).

  Key Function                Description
  --------------------------- -------------------------------------------------------------------------------------
  Data Collection             Akuisisi metrik, log, dan data konfigurasi secara real-time dan batch.
  Data Transformation         *Normalization*, *cleansing*, dan *enrichment* data mentah ke dalam format standar.
  Data Integration            Mengonsolidasikan data dari sumber yang berbeda (misalnya, BMS, PDU, OS Server).
  Data Quality & Validation   Mengimplementasikan pemeriksaan untuk memastikan akurasi dan kelengkapan data.

Use Case 1: Real-time Operational Monitoring
============================================

**Goal:** Memberikan visibilitas yang terkonsolidasi dan real-time
kepada operator DCIM mengenai status operasional semua aset data center.

  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Detail                 Description
  ---------------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------
  **Actor(s)**           *Power Distribution Units* (PDUs), *Cooling Units*, Sensor Rak, Perangkat Keras Server, Perangkat Jaringan, DCIM *Monitoring Dashboard*

  **Trigger**            *Streaming* data telemetri yang berkelanjutan (misalnya, suhu, konsumsi daya, kecepatan kipas).

  **Pre-conditions**     *Data Sources* telah dikonfigurasi dan dapat diakses melalui protokol yang ditentukan (misalnya, SNMP, Modbus, API).

  **Success Criteria**   Data yang dinormalisasi tersedia di *Asset Repository* dan *Configuration Management Database* (CMDB) dalam waktu 5 detik setelah pengumpulan.

  **Flow**               1\. **Ingestion Data:** Mengumpulkan data *time-series* mentah dari semua perangkat fisik.\
                         2. **Transformasi:** Menstandarisasi unit pengukuran (misalnya, mengonversi berbagai skala suhu ke Celsius), dan menerapkan pengidentifikasi aset umum.\
                         3. **Validasi:** Memeriksa poin data yang hilang dan *values* yang di luar jangkauan.\
                         4. **Integrasi:** Menggabungkan data sensor dengan data konfigurasi aset yang ada dari CMDB.\
                         5. **Output:** Mendorong data terintegrasi ke *Analytics & AI Engine* untuk visualisasi dan *alerting*.

  **Priority**           High
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Use Case 2: CMDB Configuration Updates
======================================

**Goal:** Memperbarui *Configuration Management Database* (CMDB) secara
otomatis dengan detail konfigurasi aset yang akurat dan terkini.

  ----------------------------------------------------------------------------------------------------------------------------------------------------------
  Detail                 Description
  ---------------------- -----------------------------------------------------------------------------------------------------------------------------------
  **Actor(s)**           *Server Provisioning System*, *Virtualization Management Platform*, *Network Discovery Tools*, CMDB

  **Trigger**            Penerapan aset baru, modifikasi aset (misalnya, peningkatan RAM), atau pemindaian penemuan (*discovery scan*) yang dijadwalkan

  **Pre-conditions**     *Integration Layer* memiliki kredensial dan akses ke API/basis data alat penemuan (*discovery tool*)

  **Success Criteria**   CMDB *records* diperbarui dengan konfigurasi terbaru dalam waktu 1 jam setelah perubahan pada sistem sumber

  **Flow**               1\. **Data Ingestion:** Mengambil *snapshot* konfigurasi atau log perubahan dari *source*.\
                         2. **Transformation:** Memetakan *source* atribut (misalnya, \'Serial No\', \'Location Tag\') ke CMDB *schema fields*.\
                         3. **Validation:** Memverifikasi bahwa *mandatory fields* telah terisi dan pengidentifikasi unik konsisten.\
                         4. **Integration:** Membandingkan data baru/terbarui dengan CMDB *records* yang ada untuk mengidentifikasi perubahan (*deltas*).\
                         5. **Output:** Memperbarui entri CMDB untuk aset yang terdampak.

  **Priority**           Medium
  ----------------------------------------------------------------------------------------------------------------------------------------------------------

Use Case 3: Log Data Unification for Security and Event Management (SIEM)
=========================================================================

**Goal:** Consolidate disparate log formats into a unified stream for
ingestion into the Security Information & Event Management (SIEM)
system. Mengonsolidasikan format log yang berbeda-beda menjadi satu
*stream* yang terpadu untuk dimasukkan ke dalam sistem *Security
Information & Event Management* (SIEM).

  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Detail                 Description
  ---------------------- --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Actor(s)**           Log Sistem Operasi (Windows Event Log, Syslog), Log Aplikasi, Log Firewall, Sistem SIEM.

  **Trigger**            Peristiwa log yang dihasilkan oleh komponen data center.

  **Pre-conditions**     Mekanisme pengiriman log (misalnya, Logstash, Filebeat) telah terinstal dan dikonfigurasi pada *source systems*.

  **Success Criteria**   Log terkait keamanan yang telah difilter dan dinormalisasi tersedia di sistem SIEM untuk dianalisis.

  **Flow**               1\. **Data Ingestion:** Receive log messages via various protocols (TCP/UDP). 2. **Transformation:** Apply parsing rules (e.g., Grok patterns) to extract key fields (timestamp, source IP, event type, severity). 3. **Filtering:** Drop non-security/non-operational relevant noise logs. 4. **Enrichment:** Add geographical or network context using external threat intelligence feeds (if applicable). 5. **Output:** Forward the standardized log event stream to the SIEM system.\
                         1. **Data Ingestion:** Menerima pesan log melalui berbagai protokol (TCP/UDP).\
                         2. **Transformation:** Menerapkan aturan *parsing* (misalnya, pola Grok) untuk mengekstrak bidang utama (*timestamp*, *source IP*, *event type*, *severity*).\
                         3. **Filtering:** Membuang log kebisingan (*noise*) yang tidak relevan dengan keamanan/operasional.\
                         4. **Enrichment:** Menambahkan konteks geografis atau jaringan menggunakan *external threat intelligence feeds* (jika ada).\
                         5. **Output:** Meneruskan *log event stream* yang telah distandarisasi ke sistem SIEM.

  **Priority**           High
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Requirements Checklist
======================

The following is a list of technical and non-functional requirements for
the Data Ingestion & Integration Layer, aligned with the above use
cases.

  Requirement Type   Requirement
  ------------------ -------------------------------------------------------------------------------------------------------
  **Technical**      Mendukung protokol SNMP v2/v3, Modbus/TCP, REST APIs, dan Syslog.
  **Technical**      *Data normalization engine* yang mendukung format JSON, XML, dan format *proprietary*.
  **Performance**    Latensi untuk data pemantauan *real-time* harus kurang dari 5 detik.
  **Performance**    Kapasitas untuk memproses *peak load* peristiwa/detik (seperti yang ditentukan pada tanggal terkait).
  **Security**       Transmisi data terenkripsi (TLS/SSL) untuk semua aliran data sensitif.
  **Scalability**    Harus dapat diskalakan secara horizontal untuk menangani pertumbuhan data center di masa depan.
