# Checklist Kepatuhan Use Case Analysis
## Data Ingestion & Integration Layer | CMDB | Asset Repository

> **Referensi Dokumen**: `docs/standar_dcim/IF-Use_Case_Analysis-FIT041-20260121.md`  
> **Task Terkait**: MT-015 — Data Synchronization for AI Models  
> **Tanggal Review**: 2026-06-12  
> **Reviewer**: Tim Infrastruktur PT. Falah Inovasi Teknologi  

---

## Bagian 1: Data Ingestion & Integration Layer

### Use Case 1: Real-time Operational Monitoring

**Goal**: Memberikan visibilitas yang terkonsolidasi dan real-time kepada operator DCIM mengenai status operasional semua aset data center.  
**Success Criteria**: Data yang dinormalisasi tersedia di Asset Repository dan CMDB dalam waktu **5 detik** setelah pengumpulan.

| # | Langkah Flow | Implementasi Aktual | Komponen | Status |
|---|---|---|---|---|
| 1 | **Ingestion**: Mengumpulkan data time-series mentah dari semua perangkat fisik | Telegraf polling Redfish, SNMP v2/v3, ISAPI setiap **120 detik** | `telegraf.service`, `configs/telegraf/*.conf`, `scripts/hikvision_poller.py` | ✅ **Terpenuhi** |
| 2 | **Transformasi**: Standarisasi unit pengukuran dan identifier aset umum | `dcim-normalizer.service` membaca topik `dcim.raw.*` → memetakan via `metric_mapping.json` → output `dcim.normalized.events` | `src/skills/telemetry/normalizer/executor.py` | ✅ **Terpenuhi** |
| 3 | **Validasi**: Pemeriksaan data hilang dan values di luar jangkauan | Payload gagal parsing dikirim ke DLQ (`dcim.dlq.parse-failure`). Threshold alerter mendeteksi nilai anomali. | `scripts/dcim_dlq_consumer.py`, `scripts/dcim_threshold_alerter.py` | ✅ **Terpenuhi** |
| 4 | **Integrasi**: Menggabungkan data sensor dengan konfigurasi aset dari CMDB | NiFi LookupRecord memanggil Enrichment API (`/enrich/{sn}`) → Redis Cache ← iTop | `dcim-enrichment-api.service`, `dcim-itop-redis-sync.service` | ✅ **Terpenuhi** |
| 5 | **Output**: Mendorong data terintegrasi ke Analytics & AI Engine | Data enriched diterbitkan ke `dcim.enriched.events` → dikonsumsi oleh ES (Kibana) dan PG (AI queries) | `telegraf-consumer.service`, `dcim-sql-consumer.service` | ✅ **Terpenuhi** |

**Requirements Checklist — UC1**:

| Requirement | Status | Catatan |
|---|---|---|
| Mendukung protokol SNMP v2/v3 | ✅ | UPS: SNMPv3; Network: SNMPv2c |
| Mendukung REST APIs | ✅ | Redfish (Server), ISAPI (CCTV) |
| Data normalization engine (JSON format) | ✅ | `metric_mapping.json` + `executor.py` |
| Latensi real-time < 5 detik | ✅ | Kafka pipeline in-memory, biasanya < 3 detik |
| Transmisi data terenkripsi | ✅ | Redfish via HTTPS; SNMP v3 dengan AES+SHA |

---

### Use Case 2: CMDB Configuration Updates

**Goal**: Memperbarui CMDB secara otomatis dengan detail konfigurasi aset yang akurat dan terkini.  
**Success Criteria**: CMDB records diperbarui dalam waktu **1 jam** setelah perubahan pada sistem sumber.

| # | Langkah Flow | Implementasi Aktual | Komponen | Status |
|---|---|---|---|---|
| 1 | **Ingestion**: Mengambil snapshot konfigurasi atau log perubahan | Redfish deep scan setiap 01:00; Kafka stream real-time setiap 120 detik | `server_inventory_to_pg.py`, `dcim-itop-unified.service` | ✅ **Terpenuhi** |
| 2 | **Transformation**: Memetakan atribut sumber ke CMDB schema fields | CPU diformat → string "2x Intel Xeon 24C/48T @ 2.8GHz"; RAM → "512 GB"; NIC → PhysicalInterface | `scripts/dcim_itop_inventory_sync.py` | ✅ **Terpenuhi** |
| 3 | **Validation**: Verifikasi mandatory fields dan konsistensi identifier | Serial number divalidasi; hostname dinormalisasi; CI dicari multi-level (SN → IP → Name) | `scripts/dcim_itop_unified_consumer.py` | ✅ **Terpenuhi** |
| 4 | **Integration**: Membandingkan data baru dengan CMDB records untuk identifikasi delta | `update_device()` hanya dipanggil jika ada perubahan; field-by-field comparison sebelum update | `scripts/dcim_itop_inventory_sync.py` | ✅ **Terpenuhi** |
| 5 | **Output**: Memperbarui entri CMDB untuk aset yang terdampak | `core/update` Server, `core/create/update` PhysicalInterface, `core/create/update` LogicalVolume | iTop REST API `localhost:8080` | ✅ **Terpenuhi** |

**Requirements Checklist — UC2**:

| Requirement | Status | Catatan |
|---|---|---|
| Dukungan model data CI fisik dan virtual | ✅ | Server, NetworkDevice, StorageSystem, PowerSource |
| Mesin pemetaan hubungan CI | ✅ | iTop: lnkServerToVolume, PhysicalInterface linked ke Server |
| CMDB diperbarui < 1 jam setelah perubahan | ✅ | Real-time via Kafka + cron 5 menit untuk hardware detail |
| RBAC untuk pembatasan update CI kritis | ✅ | iTop RBAC dikonfigurasi untuk user `admin` |

---

### Use Case 3: Log Data Unification (SIEM)

**Goal**: Mengonsolidasikan format log berbeda menjadi satu stream terpadu untuk SIEM.  
**Success Criteria**: Log terkait keamanan yang telah difilter dan dinormalisasi tersedia di SIEM.

| # | Langkah Flow | Implementasi Aktual | Status |
|---|---|---|---|
| 1 | **Ingestion**: Terima pesan log via TCP/UDP | Kafka menampung semua event dari pipeline | ✅ **Terpenuhi (parsial)** |
| 2 | **Transformation**: Parsing untuk ekstrak timestamp, source IP, event type | Normalizer mengekstrak field utama ke CDM schema | ✅ **Terpenuhi** |
| 3 | **Filtering**: Buang noise log non-security | Alert threshold memfilter event signifikan | ⚠️ **Parsial** — Dedicated SIEM belum terimplementasi |
| 4 | **Enrichment**: Tambah konteks dari threat intelligence | Belum ada integrasi threat intelligence feed | ❌ **Belum Terpenuhi** |
| 5 | **Output**: Forward ke sistem SIEM | Log tersimpan di Elasticsearch; belum ada dedicated SIEM | ⚠️ **Parsial** — Elasticsearch berperan sebagai log store, bukan SIEM penuh |

> **Catatan**: SIEM sebagai sistem tersendiri belum diimplementasikan. Elasticsearch + Kibana berfungsi sebagai pengganti sementara untuk log centralization dan alerting operasional. Dashboard Kibana Log Terpusat (`dcim-log-dashboard`) kini telah beroperasi penuh dengan parser JSON (`decode_json_fields`) untuk melacak event error/warning secara realtime.

---

## Bagian 2: Configuration Management Database (CMDB)

### Use Case 1: Incident Impact Analysis and Root Cause Identification

**Goal**: Menentukan dengan cepat layanan dan unit bisnis yang terpengaruh oleh insiden infrastruktur.  
**Success Criteria**: Operator dapat menghasilkan daftar CI dan layanan yang terpengaruh dalam **30 detik**.

| # | Langkah Flow | Implementasi Aktual | Komponen | Status |
|---|---|---|---|---|
| Input | Sistem Manajemen Insiden meminta data dari CMDB | Alert di Kibana → manual query ke iTop | Kibana, iTop | ⚠️ **Parsial** |
| Pencarian Hubungan | CMDB melintasi grafik hubungan | iTop memiliki relasi CI: Server-to-Rack, lnkServerToVolume, PhysicalInterface | iTop Relationship Engine | ✅ **Terpenuhi** |
| Pemetaan Dampak | CI yang bergantung dipetakan ke layanan bisnis | Hubungan CI tersedia di iTop; namun mapping ke layanan bisnis belum dikonfigurasi | iTop | ⚠️ **Parsial** |
| Output | Menampilkan peta dampak visual | Kibana Dashboard menampilkan device-level impact; iTop dapat di-query manual | Kibana, iTop | ⚠️ **Parsial** |

**Requirements Checklist — CMDB UC1**:

| Requirement | Status | Catatan |
|---|---|---|
| Model data CI: fisik, virtual, logis | ✅ | Server, NIC, Disk, StorageSystem, Rack, Location semua ada di iTop |
| Pemetaan ketergantungan CI yang kompleks | ✅ | iTop `lnkServerToVolume`, `connectableci_id` |
| Penelusuran hubungan CI (kedalaman 5) < 500ms | ⚠️ | Bergantung pada performa iTop instance lokal; belum diukur formal |
| RBAC untuk pembatasan update CI kritis | ✅ | iTop RBAC aktif |

---

### Use Case 2: Change Verification and Audit Compliance

**Goal**: Memastikan semua perubahan infrastruktur sesuai kebijakan dan memverifikasi state terhadap baseline.  
**Success Criteria**: CMDB menandai konfigurasi drift dalam **15 menit** setelah terdeteksi.

| # | Langkah Flow | Implementasi Aktual | Status |
|---|---|---|---|
| Perubahan Masukan | Change Management mencatat perubahan yang disetujui | Belum ada Change Management System terintegrasi | ❌ **Belum Terpenuhi** |
| Pengambilan Data | Ambil status konfigurasi aktual | `dcim_itop_inventory_sync.py` membandingkan data PG vs iTop setiap 5 menit | ✅ **Terpenuhi** |
| Perbandingan | Bandingkan state aktual vs baseline | Delta detection dilakukan sebelum setiap update ke iTop | ✅ **Terpenuhi** |
| Verifikasi | Jika sesuai, update baseline | iTop diperbarui hanya jika ada perubahan signifikan | ✅ **Terpenuhi** |
| Audit/Drift | Jika menyimpang, kirim alert | Belum ada alert khusus untuk configuration drift | ⚠️ **Parsial** |

---

### Use Case 3: Asset Lifecycle Management and Capacity Planning

**Goal**: Menyediakan inventarisasi akurat untuk semua aset dan mendukung perencanaan kapasitas.  
**Success Criteria**: Asset Manager dapat menghasilkan laporan aset yang dijadwalkan decommission dalam 90 hari dengan akurasi 100%.

| # | Langkah Flow | Implementasi Aktual | Status |
|---|---|---|---|
| Query | Kapasitas Tool meminta daftar semua CI "In Use" | iTop OQL: `SELECT Server WHERE status = 'production'` | ✅ **Terpenuhi** |
| Filtering & Atribut | Filter CI berdasarkan status, ambil atribut kunci | iTop menyimpan CPU, RAM, lokasi; Ralph menyimpan data finansial | ✅ **Terpenuhi** |
| Integrasi | CMDB ekspor ke Sistem Keuangan | `itop_to_ralph_sync.py` mengisi Ralph dengan data aset | ✅ **Terpenuhi** |
| Pembaruan | Saat aset dinonaktifkan, update status ke "Decommissioned" | Manual update di iTop; decommission log di `docs/operations/decommission-log.md` | ⚠️ **Parsial — masih manual** |

**Requirements Checklist — CMDB UC3**:

| Requirement | Status | Catatan |
|---|---|---|
| Atribut siklus hidup (tanggal beli, garansi, status) | ⚠️ | Status ✅ (iTop); tanggal beli/garansi ⚠️ (harus diisi manual via `import_financial_data_to_itop.py`) |
| CI dapat dihasilkan laporan decommission 90 hari | ⚠️ | Perlu OQL query manual di iTop; belum ada laporan otomatis |

---

## Bagian 3: Asset Repository (Ralph)

### Use Case 1: Physical Asset Audit and Inventory Reconciliation

**Goal**: Memungkinkan operator untuk melakukan audit fisik dan mencocokkan aset aktual dengan inventaris tercatat.  
**Success Criteria**: Repositori dapat memverifikasi keberadaan dan lokasi 100% aset kritis dalam **5 menit** setelah audit selesai.

| # | Langkah Flow | Implementasi Aktual | Status |
|---|---|---|---|
| Input | Operator memindai tag aset | Tidak ada QR/RFID scanner terintegrasi; identifikasi via hostname/IP | ❌ **Belum Terpenuhi** |
| Query | Akses Asset Repository via unique ID | Ralph API: `GET /api/data-center-assets/?hostname=SERVER-HCI-01` | ✅ **Terpenuhi** |
| Validasi | Repositori mengembalikan lokasi dan atribut yang diharapkan | Ralph menampilkan rack position, status, komponen hardware | ✅ **Terpenuhi** |
| Rekonsiliasi | Identifikasi ketidaksesuaian | `itop_to_ralph_sync.py` melakukan pruning komponen yang tidak lagi terdeteksi | ✅ **Terpenuhi** |
| Output | Operator menerima feedback status dan lokasi aset | Via Ralph Web UI (`localhost:8082`) | ✅ **Terpenuhi** |

**Requirements Checklist — Asset Repo UC1**:

| Requirement | Status | Catatan |
|---|---|---|
| Identifikasi unik per aset (Serial, Asset Label) | ✅ | Serial number & asset_number diisi otomatis dari Redfish |
| Field data lokasi geometris (Rack, U-Start, U-End) | ✅ | Ralph `position` dan `slot_number` terisi via sync |
| Pencarian aset < 10ms | ✅ | Ralph REST API dengan indeks database |

---

### Use Case 2: Reservation and Deployment of New Assets

**Goal**: Memfasilitasi provisioning dengan mengalokasikan ruang rack dan memastikan aset baru di lokasi yang benar.

| # | Langkah Flow | Implementasi Aktual | Status |
|---|---|---|---|
| Permintaan | Provisioning System mengirimkan spesifikasi aset baru | Belum ada integrasi otomatis dengan provisioning system | ❌ **Belum Terpenuhi** |
| Pemeriksaan Kapasitas | Mencari rack dengan kapasitas tersedia | Ralph menampilkan rack utilization; tidak ada otomasi pencarian slot | ⚠️ **Parsial — manual** |
| Pemesanan | Tandai U-space sebagai "Reserved" | Manual di Ralph Web UI | ⚠️ **Parsial — manual** |
| Pembaruan | Update status dari "Reserved" ke "In Use" | `dcim-itop-unified.service` auto-create CI saat data masuk Kafka; Ralph diperbarui via daily sync | ✅ **Terpenuhi (setelah install)** |

---

### Use Case 3: Financial Reporting and Depreciation Calculation

**Goal**: Menyediakan atribut aset yang akurat untuk Sistem Keuangan menghitung depresiasi dan CapEx.  
**Success Criteria**: Sistem Keuangan dapat menghasilkan laporan inventarisasi lengkap dengan semua data keuangan.

| # | Langkah Flow | Implementasi Aktual | Status |
|---|---|---|---|
| Permintaan | Financial System request laporan ke Asset Repository | Ralph REST API tersedia untuk query; belum ada integrasi langsung ke sistem keuangan | ⚠️ **Parsial** |
| Query | Ambil semua aset "In Use" dengan atribut keuangan | Ralph: `GET /api/data-center-assets/?status=in_use` tersedia | ✅ **Terpenuhi** |
| Pengambilan Data | Tanggal beli, biaya akuisisi, umur pakai | `docs/operations/asset-financial-data-template.csv` + `scripts/import_financial_data_to_itop.py` | ⚠️ **Parsial — import manual** |
| Output | Data dalam format standar (CSV/API) | Ralph API mengembalikan JSON; konversi ke CSV butuh skrip tambahan | ⚠️ **Parsial** |
| Pemeliharaan | Data keuangan aset baru dimasukkan ke Repositori | `import_financial_data_to_itop.py` tersedia namun belum dijadwalkan otomatis | ⚠️ **Parsial** |

**Requirements Checklist — Asset Repo UC3**:

| Requirement | Status | Catatan |
|---|---|---|
| Atribut keuangan: tanggal beli, biaya, garansi | ⚠️ | Template tersedia (`asset-financial-data-template.csv`); pengisian masih manual |
| Export ke Sistem Keuangan dalam format standar | ⚠️ | Ralph API tersedia; belum ada connector ke ERP/sistem keuangan |
| RBAC untuk atribut keuangan | ✅ | Ralph memiliki permission system per model |

---

## Ringkasan Kepatuhan Keseluruhan

| Domain | Use Case | Status |
|---|---|---|
| **Data Ingestion** | UC1: Real-time Monitoring | ✅ Terpenuhi |
| **Data Ingestion** | UC2: CMDB Config Updates | ✅ Terpenuhi |
| **Data Ingestion** | UC3: Log Unification (SIEM) | ⚠️ Parsial |
| **CMDB** | UC1: Incident Impact Analysis | ⚠️ Parsial |
| **CMDB** | UC2: Change Verification | ⚠️ Parsial |
| **CMDB** | UC3: Asset Lifecycle & Capacity | ⚠️ Parsial |
| **Asset Repository** | UC1: Physical Audit & Reconciliation | ⚠️ Parsial |
| **Asset Repository** | UC2: Reservation & Deployment | ⚠️ Parsial |
| **Asset Repository** | UC3: Financial Reporting | ⚠️ Parsial |

### Legenda
- ✅ **Terpenuhi** — Implementasi sudah ada dan berjalan sesuai kriteria sukses
- ⚠️ **Parsial** — Implementasi sebagian ada; memerlukan penyempurnaan atau integrasi tambahan
- ❌ **Belum Terpenuhi** — Belum ada implementasi untuk requirement ini

### Prioritas Gap yang Perlu Ditangani

1. **[SELESAI]** Aktivasi `dcim-data-quality-check.timer` (Sudah diaktifkan dan berjalan otomatis setiap pukul 06:00).
2. **[Tinggi]** Jadwalkan `import_financial_data_to_itop.py` secara berkala agar data keuangan aset tersinkronisasi.
3. **[Sedang]** Implementasi SIEM terpisah atau integrasi Elasticsearch dengan security correlation rules.
4. **[Sedang]** Integrasi Change Management System dengan iTop untuk audit trail perubahan konfigurasi
5. **[Rendah]** Otomasi scanning/reservasi rack slot di Ralph untuk workflow provisioning aset baru
