# Arsitektur Telegraf Producer dan Consumer pada Pipeline DCIM

Dokumen ini menjelaskan pembagian peran (separation of duties) antara **Telegraf Producer** dan **Telegraf Consumer** dalam pipeline metrik DCIM berbasis Kafka, beserta detail konfigurasi dan contoh aliran datanya.

## 1. Pemisahan Peran (Separation of Duties)

Sebelumnya, sebuah instans Telegraf tunggal bertugas mengambil data dari perangkat keras (polling) sekaligus mengirimkannya langsung ke Elasticsearch. Desain ini menimbulkan masalah berupa duplikasi data dan inefisiensi ketika pipeline metrik harus disisipi layer pengayaan data (Enrichment via Apache NiFi dan Python Normalizer).

Untuk mengatasi masalah tersebut, peran Telegraf dipisah menjadi dua instans mandiri:

1.  **Telegraf Producer (`telegraf.service`)**: Bertugas **hanya** untuk melakukan *polling* (mengumpulkan data) dari perangkat fisik (SNMP, Redfish, HTTP) dan mengirimkan data mentah tersebut ke topik `dcim.raw.*` di Kafka.
2.  **Telegraf Consumer (`telegraf-consumer.service`)**: Bertugas **hanya** untuk mendengarkan (consume) data yang sudah melalui proses pengayaan (enrichment) dari topik `dcim.enriched.events` di Kafka, kemudian menyusun dan mengirimkan data akhir tersebut ke indeks **`dcim-metrics-unified-*`** di Elasticsearch.

Pemisahan ini menjamin:
*   Tidak ada duplikasi data di Elasticsearch.
*   Skalabilitas: Kafka mampu menampung lonjakan data mentah dari *Producer* jika Elasticsearch sedang melambat, sehingga *Consumer* bisa menyesuaikan kecepatan bacanya.
*   Arsitektur yang bersih: Data yang masuk ke Elasticsearch dipastikan sudah melewati layer normalisasi (Standardisasi field) dan *enrichment* (Penambahan data Site, Rack, dll).

---

## 2. Telegraf Producer (`telegraf.service`)

**Lokasi Konfigurasi**: `/etc/telegraf/telegraf.d/*.conf`

*Producer* dikonfigurasi melalui berbagai file `.conf` (seperti `network-snmp.conf`, `servers-redfish.conf`) yang mengatur protokol pengambilan data sesuai perangkat. Setiap konfigurasi menggunakan output `kafka` untuk mendistribusikan data ke topik mentah (raw).

### Contoh Konfigurasi Output (Kafka Producer)
```toml
[[outputs.kafka]]
  brokers = ["10.70.0.56:9092"]
  topic = "dcim.raw.network.snmp"
  data_format = "json"
```

### Contoh Data yang Dihasilkan (Raw Data ke Kafka)
Data yang dikirimkan oleh *Producer* ke topik `dcim.raw.network.snmp` berisi struktur bawaan Telegraf yang belum memiliki konteks lokasi atau penamaan metrik yang seragam.

```json
{
  "fields": {
    "ifHCInOctets": 2558159558,
    "ifHCOutOctets": 2817887035,
    "ifOperStatus": 1
  },
  "name": "interface",
  "tags": {
    "hostname": "FIT-DIST-SW-LAN1",
    "ip": "172.16.35.3",
    "device_type": "network_switch"
  },
  "timestamp": 1777513086
}
```

*Data di atas kemudian diproses oleh `dcim-normalizer` dan `Apache NiFi` sebelum siap diambil oleh Consumer.*

---

## 3. Telegraf Consumer (`telegraf-consumer.service`)

**Lokasi Konfigurasi**: `/etc/telegraf/telegraf-consumer.conf`

*Consumer* mengambil data dari ujung akhir pipeline (keluaran NiFi) dan meneruskannya ke Elasticsearch. Karena data yang keluar dari NiFi memiliki skema JSON yang flat (datar), konfigurasi *Consumer* menggunakan `data_format = "json"` (v1) dengan menetapkan field mana saja yang bertindak sebagai *tags* vs *metrics*.

### Detail Konfigurasi (Kafka Consumer ke Elasticsearch)
```toml
[agent]
  interval = "10s"
  hostname = "srv-rnd-dcim-consumer"

[[inputs.kafka_consumer]]
  brokers = ["10.70.0.56:9092"]
  topics = ["dcim.enriched.events"]
  consumer_group = "telegraf_unified_consumer"
  offset = "oldest"
  
  # Format JSON v1 untuk parsing struktur flat
  data_format = "json"
  
  # Mendefinisikan field yang akan diindeks sebagai keyword (label)
  tag_keys = [
    "hostname",
    "ip",
    "serial_number",
    "device_type",
    "severity",
    "site",
    "rack",
    "measurement",
    "metric_name"
  ]
  
  # Pemetaan waktu
  json_time_key = "timestamp"
  json_time_format = "unix"

[[outputs.elasticsearch]]
  urls = ["https://10.70.0.56:9200"]
  username = "elastic"
  password = "***"
  index_name = "dcim-metrics-unified-%Y.%m.%d"
  manage_template = true
  template_name = "dcim-metrics-unified"
```

### Contoh Data yang Diterima (Enriched Data dari Kafka)
Data yang ditarik oleh *Consumer* dari topik `dcim.enriched.events` sudah berformat standar dan kaya akan konteks metadata dari CMDB (Ralph).

```json
{
  "event_id": "9a4b970a-ce11-4f77-8282-7a109c90889f",
  "event_time": "2026-04-30T01:38:06+00:00",
  "timestamp": 1777513086,
  "source_topic": "dcim.raw.network.snmp",
  "measurement": "dcim_network_storage",
  "device_type": "network_switch",
  "hostname": "FIT-DIST-SW-LAN1",
  "ip": "172.16.35.3",
  "serial_number": "HF8091GRXMZ",
  "metric_name": "interface_status",
  "metric_value": 1,
  "severity": "info",
  "site": "Local Instance",
  "rack_name": "Rack Server 1",
  "rack_position": 35
}
```

### Contoh Data yang Dikirim ke Elasticsearch (Final Indexed Document)
Berdasarkan aturan `tag_keys` pada konfigurasi, Telegraf akan memetakan atribut di atas dan memformatnya agar sesuai dengan skema Elasticsearch.

```json
{
  "@timestamp": "2026-04-30T01:38:06Z",
  "measurement_name": "kafka_consumer",
  "tag": {
    "hostname": "FIT-DIST-SW-LAN1",
    "ip": "172.16.35.3",
    "serial_number": "HF8091GRXMZ",
    "device_type": "network_switch",
    "severity": "info",
    "site": "Local Instance",
    "rack": "Rack Server 1",
    "measurement": "dcim_network_storage",
    "metric_name": "interface_status"
  },
  "kafka_consumer": {
    "metric_value": 1,
    "rack_position": 35,
    "timestamp": 1777513086
  }
}
```

*(Catatan: Nilai dinamis diletakkan di dalam objek `kafka_consumer`, sementara label untuk filter dan agregasi diletakkan di dalam objek `tag`.)*
