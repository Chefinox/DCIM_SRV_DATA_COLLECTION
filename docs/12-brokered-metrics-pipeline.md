# DCIM Brokered Metrics Pipeline Documentation

Dokumen ini menjelaskan arsitektur pengumpulan metrics infrastruktur menggunakan **Apache Kafka** sebagai message broker.

> [!NOTE]
> Pipeline sebelumnya menggunakan RabbitMQ. Per **2026-04-22**, broker telah dimigrasikan ke **Apache Kafka** untuk mendukung kebutuhan AI/ML dan high-throughput streaming.

---

## 1. Arsitektur Data Flow

Metrics dikumpulkan dari perangkat fisik dan disalurkan melalui beberapa tahapan sebelum sampai ke dashboard visualisasi.

### Alur Kerja:
1. **Pollers (Producers)**: Telegraf Agent mengambil data via SNMP, Redfish, dan ISAPI.
2. **Broker (Apache Kafka)**: Menampung metrics di topic `dcim.standardized.metrics`. Data tersimpan di disk; consumer bisa crash dan tetap membaca dari posisi terakhir.
3. **Consumer**: Layanan `telegraf-consumer` membaca topic Kafka dan mendistribusikan data ke dua tujuan (Dual Output).
4. **Storage**:
   - **Elasticsearch**: Untuk analisis deret waktu dan visualisasi di Kibana.
   - **PostgreSQL**: *(Dinonaktifkan sementara — skema tabel perlu sinkronisasi)*.

---

## 2. Detail Komponen Layanan

### A. Telegraf Producer
- **Service**: `telegraf.service`
- **Config**: `/etc/telegraf/telegraf.conf` + `/etc/telegraf/telegraf.d/*.conf`
- **Output**: `outputs.kafka` → `127.0.0.1:9092`, topic `dcim.standardized.metrics`

### B. Apache Kafka Broker
- **Container**: `kafka-broker` (Docker)
- **Image**: `apache/kafka:latest`
- **Port**: `9092`
- **Mode**: KRaft (tanpa Zookeeper)
- **Compose**: `/home/infra/dcim_metrics_project/kafka/docker-compose.yml`

### C. Telegraf Consumer
- **Service**: `telegraf-consumer.service`
- **Config**: `/etc/telegraf/telegraf-consumer.conf`
- **Input**: `inputs.kafka_consumer` — topic `dcim.standardized.metrics`, group `telegraf_es_consumer`
- **Output 1**: ES index `dcim-inventory-%Y.%m.%d` (namepass: `dcim_inventory`)
- **Output 2**: ES index `telegraf-{device_type}-%Y.%m.%d` (namedrop: `dcim_inventory`)

---

## 3. Perintah Operasional

| Kebutuhan | Perintah |
| :--- | :--- |
| Restart Producer | `sudo systemctl restart telegraf` |
| Restart Consumer | `sudo systemctl restart telegraf-consumer` |
| Log Producer | `sudo journalctl -u telegraf -f` |
| Log Consumer | `sudo journalctl -u telegraf-consumer -f` |
| Cek Kafka Container | `docker ps \| grep kafka-broker` |
| Cek Data di Kafka | `docker exec -it kafka-broker /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic dcim.standardized.metrics` |
| Cek Consumer Lag | `docker exec -it kafka-broker /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group telegraf_es_consumer` |
| Restart Kafka | `cd /home/infra/dcim_metrics_project/kafka && docker compose restart` |

---

## 4. Status Komponen (per 2026-04-22)

| Komponen | Status | Keterangan |
|:---|:---|:---|
| `kafka-broker` | ✅ Running | Port 9092, mode KRaft |
| `telegraf.service` | ✅ Running | Producer → Kafka |
| `telegraf-consumer.service` | ✅ Running | Kafka → Elasticsearch |
| `outputs.sql` (PostgreSQL) | ⚠️ Off | Kolom `lower_threshold_critical` tidak ada di tabel |
| Referensi Lengkap | 📄 [19-kafka-pipeline-architecture.md](./19-kafka-pipeline-architecture.md) | |

---

*Terakhir diupdate: 2026-04-22 — Migrasi RabbitMQ → Apache Kafka selesai*
