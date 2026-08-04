# Laporan Post-Mortem Insiden: Kehilangan Data Backlog Kafka Akibat Ephemeral Log Directory

**Tanggal Insiden**: 03 – 04 Agustus 2026  
**Penyusun**: Imam Syauqi Achmad  
**Sistem Terdampak**: Apache Kafka Broker Cluster (`kafka1`, `kafka2`, `kafka3`)  
**Tingkat Keparahan**: High (Kehilangan antrean buffer pesan uncommitted)  
**Status Insiden**: Selesai / Tuntas (Perbaikan Persistensi Diimplementasikan)

---

## 1. Ringkasan Eksekutif

Pada tanggal 03 Agustus 2026, dilakukan proses upgrade Apache Kafka 3.7.0 ke 4.1.2 pada cluster 3-node co-located (`srv-rnd-dcim`). Setelah proses restart serentak (coordinated simultaneous cutover) berhasil dilakukan, ditemukan bahwa antrean backlog pesan (~3,6 juta pesan) pada Kafka buffer ter-reset. 

Investigasi mendalam menunjukkan bahwa variabel environment `KAFKA_LOG_DIRS` **tidak pernah dikonfigurasikan** pada file `docker-compose-cluster.yml`. Hal ini menyebabkan Apache Kafka secara default menulis seluruh log segmen data ke direktori ephemeral container **`/tmp/kafka-logs`**, bukan ke volume persisten. Ketika container di-recreate saat proses upgrade, direktori ephemeral tersebut terhapus bersama container lama.

Keputusan resmi diambil untuk menerima kehilangan antrean backlog pesan lama yang belum terproses, memverifikasi integritas seluruh database hilir (PostgreSQL, Elasticsearch, TimescaleDB, iTop CMDB), dan segera mengimplementasikan perbaikan persistensi bernama (Named Volume) agar insiden ini tidak dapat terulang kembali.

---

## 2. Kronologi Kejadian

- **03 Agustus 2026 (15:42 WIB)**: Dilakukan upgrade Kafka 3.7.0 ke 4.1.2 menggunakan metode *Coordinated Simultaneous Cutover* (`docker stop` seluruh broker disusul `docker compose up -d`). Downtime berlangsung selama 12 detik.
- **03 Agustus 2026 (15:43 WIB)**: Kafka 4.1.2 berhasil booting 100% tanpa error `INCONSISTENT_CLUSTER_ID`. Quorum KRaft terbentuk sempurna.
- **03 Agustus 2026 (16:00 WIB)**: Terdeteksi `LeaderEpoch` ter-reset ke 3 dan `PartitionCount` seluruh topik `dcim.*` berubah menjadi 1 partisi.
- **04 Agustus 2026 (01:43 WIB)**: Audit `docker inspect` dan inspeksi file system container menemukan bahwa `/var/lib/kafka/data` (mount volume) kosong total, sedangkan Kafka menulis data ke `/tmp/kafka-logs` karena variabel `KAFKA_LOG_DIRS` tidak terpasang.
- **04 Agustus 2026 (02:14 WIB)**: Perbaikan `docker-compose-cluster.yml` diterapkan dengan menambahkan `KAFKA_LOG_DIRS: /var/lib/kafka/data` dan named volume (`kafka1_data`, `kafka2_data`, `kafka3_data`). Broker di-restart dan terverifikasi menulis log ke volume persisten.
- **04 Agustus 2026 (02:19 WIB)**: Seluruh 13 topik `dcim.*` di-restore ke 12 partisi dengan `min.insync.replicas=2`.

---

## 3. Akar Masalah (Root Cause)

1. **Missing `KAFKA_LOG_DIRS` Environment Variable**:  
   Official image `apache/kafka` secara default mengarahkan log storage ke `/tmp/kafka-logs` apabila variabel `KAFKA_LOG_DIRS` tidak didefinisikan secara eksplisit.
2. **Unused Anonymous Volume**:  
   Spesifikasi compose awal hanya me-mount `./certs:/etc/kafka/secrets`, sehingga Docker membuat anonymous volume bawaan image ke `/var/lib/kafka/data`. Namun karena Kafka menulis ke `/tmp/kafka-logs`, volume tersebut tidak pernah terisi.
3. **Container Lifecycle Disconnection**:  
   Saat perintah `docker compose up -d` dieksekusi dengan tag image baru (`4.1.2`), container lama beserta layer filesystem ephemeral `/tmp/kafka-logs` dihancurkan, sehingga antrean pesan di buffer Kafka hilang.

---

## 4. Dampak Insiden

- **Dampak Buruk**:
  - Kehilangan backlog pesan uncommitted (~3,6 juta pesan telemetri historis pada buffer Kafka).
  - Penurunan sementara jumlah partisi topik `dcim.*` menjadi 1 partisi saat metadata KRaft ter-reset.
- **Status Data Hilir (Terkonfirmasi Safe & Intact)**:
  - **TimescaleDB (`dcim_analytics`)**: 39,88 juta record telemetri utuh.
  - **PostgreSQL (`dcim_sot`)**: 101 data aset & tabel partisi `dcim_events` utuh.
  - **Elasticsearch (`dcim_elasticsearch`)**: Cluster health status yellow/green, data index terproses utuh.
  - **iTop CMDB**: 42 Server CIs terdaftar dan tersinkronisasi utuh.

---

## 5. Tindakan Remediasi yang Diimplementasikan

1. **Konfigurasi Log Path Persisten Eksplisit**:
   Menambahkan `KAFKA_LOG_DIRS: /var/lib/kafka/data` di ketiga service Kafka pada `docker-compose-cluster.yml`.
2. **Penggunaan Named Volume**:
   Mendeklarasikan top-level volume `kafka1_data`, `kafka2_data`, `kafka3_data` agar data tersimpan di volume Docker persisten host (`/var/lib/docker/volumes/kafkaX_data/_data`).
3. **Restorasi Topik & Re-balancing**:
   Mengembalikan seluruh 13 topik `dcim.*` ke 12 Partisi dan `min.insync.replicas=2`.
4. **Verifikasi Runtime**:
   Memastikan consumer groups (`dcim_python_normalizer_group`, `dcim-es-consumer`, dll.) terhubung kembali dan mengonsumsi telemetri realtime secara terdistribusi di 12 partisi.

---

## 6. Pelajaran & Rekomendasi Masa Depan

- **Pemeriksaan Storage Mount**: Setiap perubahan service Docker harus selalu memverifikasi variabel environment storage (`LOG_DIR`/`DATA_DIR`) dan memastikan data ditulis ke path mount yang benar.
- **Pemisahan Log Metadata & Data Topik**: Melakukan monitoring penggunaan disk pada volume Kafka persisten melalui Prometheus Exporter.
