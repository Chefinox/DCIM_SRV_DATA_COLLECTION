# DCIM AI-Readiness Assessment & Pipeline Audit

Dokumen ini adalah evaluasi komprehensif mengenai tingkat kesiapan ekosistem Data Center Infrastructure Management (DCIM) untuk diintegrasikan dengan model *Artificial Intelligence* (AI) dan *Machine Learning* (ML) pada kuartal mendatang.

---

## 🌟 Ringkasan Eksekutif

Transisi dari arsitektur RabbitMQ warisan ke **Unified Kafka Pipeline v3.4** telah menyelesaikan hambatan utama dalam penyerapan dan standardisasi data. Sistem kini memiliki dua jalur terpisah yang dioptimalkan: **Jalur Cepat** (untuk aliran telemetri berkecepatan tinggi) dan **Jalur Lambat** (untuk Source of Truth inventaris perangkat keras). Secara arsitektural, pipeline data ini sudah dinilai **Sangat Siap (Highly AI-Ready)** untuk skenario pemrosesan data, dengan beberapa catatan mengenai akumulasi data historis.

---

## 📊 Kriteria AI-Readiness dan Pencapaian

Berikut adalah penjabaran poin-poin standar industri untuk kesiapan AI dan status implementasinya di DCIM kita:

### 1. Data Normalization & Schema Consistency (Konsistensi Skema)
Model AI membutuhkan format data yang dapat diprediksi tanpa harus menebak-nebak tipe atau struktur *field*.
*   **Status: ✅ MEMENUHI (TERCAPAI TINGGI)**
*   **Apa yang dilakukan:** 
    * Mengganti format data yang tumpang tindih dengan **Unified Elasticsearch Schema** (`dcim-metrics-unified-*`).
    * Implementasi *Starlark Processor* di Telegraf untuk merapikan seluruh *raw metric* ke dalam struktur `[measurement].raw_fields_*` (misal: `interface.raw_fields_ifInOctets`).
    * Data metrik yang spesifik secara otomatis dinamakan sesuai nama pengukurannya tanpa mencemari metadata universal.

### 2. Contextual Enrichment (Pengayaan Konteks Bisnis)
Model ML tidak bisa membedakan tingkat kekritisan jika data hanya berupa "CPU 90% pada IP 10.0.0.1". AI membutuhkan lokasi dan kepemilikan aset.
*   **Status: ✅ MEMENUHI**
*   **Apa yang dilakukan:**
    * Membangun aliran pengayaan terpusat: `Ralph CMDB` → `PostgreSQL` → `Redis Cache` → `Apache NiFi`.
    * Setiap paket data kini diinjeksi dengan `Universal Tags` di tingkat Elasticsearch, yang secara otomatis melampirkan konteks: `site`, `rack_name`, `environment` (Production/Staging), `business_unit`, `manufacturer`, dan `model`. 
    * AI kini dapat melakukan *clustering* anomali berdasarkan Vendor atau Lokasi Rak spesifik secara terstruktur.

### 3. Scalability & Low Latency Streaming (Aliran Berkecepatan Tinggi)
AI modern (terutama untuk deteksi anomali *real-time* atau *AIOps*) membutuhkan platform data (*Message Bus*) yang sanggup menerima jutaan metrik per menit tanpa *bottleneck*.
*   **Status: ✅ MEMENUHI**
*   **Apa yang dilakukan:**
    * Migrasi dari RabbitMQ (AMQP) yang cenderung *blocking* ke **Apache Kafka**.
    * Penyeragaman interval polling Telegraf ke *Fast Path* menjadi **120 detik** yang konstan (dari sebelumnya yang acak dan membebani jaringan keras).
    * Sinkronisasi arsitektur *consumer* yang tidak akan menciptakan *lag* pada sistem, memastikan AI Engine nanti bisa ber-langganan (subscribe) langsung ke topik `dcim.enriched.events`.

### 4. Ground Truth Integrity (Integritas Master Data)
AI akan menghasilkan "halusinasi" atau alarm palsu (False Positive) jika daftar perangkat keras yang ada di CMDB berbeda dengan realita (*ghost assets*).
*   **Status: ✅ MEMENUHI**
*   **Apa yang dilakukan:**
    * Menonaktifkan sistem sinkronisasi lama (`server_deep_sync.py`) yang berpotensi menyebabkan duplikasi data.
    * Menetapkan **PostgreSQL (`dcim_events`) sebagai Single Source of Truth**.
    * Menerapkan logika *Pruning* otomatis pada `ralph_cmdb_sync.py` (berjalan Pukul 02:00) yang didahului oleh pengambilan *snapshot* fisik via Redfish (Pukul 01:00).
    * Penambahan dukungan validasi otomatis untuk Server, UPS, Network Switch, NAS, CCTV, dan NVR berdasarkan *Primary Key* `serial_number`.

---

## 🚧 Poin Evaluasi yang Belum Sepenuhnya Memenuhi (Future Work)

Meskipun infrastruktur pipanya (Pipeline) sudah AI-Ready, data itu sendiri masih membutuhkan waktu sebelum bisa dilatih (*Training*):

### 5. Historical Data Accumulation (Akumulasi Volume Historis)
*   **Status: ⚠️ BELUM MEMENUHI (BUTUH WAKTU)**
*   **Analisis:** Algoritma ML untuk memprediksi kerusakan *hardware* (Predictive Maintenance) biasanya membutuhkan data *baseline* historis minimal 3-6 bulan dari metrik seperti suhu, RPM kipas, dan voltase power. Karena arsitektur skema baru saja difinalisasi dan distandardisasi pada Q2 2026, kita memiliki keterbatasan data historis yang bersih sebelum tanggal tersebut. 
*   **Tindakan:** Membiarkan *pipeline* berjalan stabil tanpa modifikasi skema besar-besaran untuk membangun *dataset* bersih.

### 6. Labeled Data for Supervised Learning (Pelabelan Data Anomali)
*   **Status: ⚠️ BELUM MEMENUHI**
*   **Analisis:** Saat ini sistem baru mencatat status operasional, namun tidak ada "Catatan Insiden" langsung yang terhubung dengan metrik (misal saat server benar-benar mati/kebakaran). AI untuk sementara hanya bisa menggunakan metode *Unsupervised Learning* (mencari penyimpangan pola) daripada klasifikasi definitif kerusakan.
*   **Tindakan:** Mengintegrasikan sistem *Ticketing* (Jira/ITSM) dengan Elasticsearch di masa depan, di mana tiket gangguan *hardware* menjadi label waktu insiden untuk dipelajari oleh model ML.

### 7. Data Quality Observability (Deteksi Pergeseran Skema)
*   **Status: 🟡 PARSIAL**
*   **Analisis:** Pipeline sudah berjalan lancar, namun jika esok hari ada pembaruan *firmware* Mikrotik yang mengubah format SNMP MIB, data akan secara diam-diam hilang (*silent drop*) atau masuk ke *raw_fields* dengan nama yang salah, yang merusak prediksi AI.
*   **Tindakan:** Perlu ada pembuatan *Dashboard Data Quality* yang membunyikan alarm jika rasio metrik harian tiba-tiba turun atau ada field `raw_fields_X` yang mendadak tidak terbaca.

---

## 🎯 Kesimpulan

Fondasi **Data Engineering** telah rampung sepenuhnya. Proyek DCIM kini telah beralih dari fase perbaikan *Pipeline* / *Plumbing* menjadi platform **Observability & Intelligence**. Data yang mengalir hari ini sudah sangat bersih, diperkaya, dinormalisasi, dan terpusat dalam satu standar skema Elasticsearch, memungkinkan inisiatif integrasi AI (seperti deteksi anomali suhu proaktif dan klasterisasi peringatan insiden) segera dimulai.
