# Panduan Pengujian End-to-End (E2E) Pipeline DCIM v4.0

Dokumen ini berisi panduan komprehensif untuk menguji dan melacak aliran data dari awal hingga akhir pada arsitektur pipeline DCIM v4.0. Pengujian ini berguna untuk _troubleshooting_, memastikan keandalan sistem, dan audit kualitas data di setiap lapisan (layer).

## Arsitektur Pipeline v4.0
Aliran data bergerak melewati 5 lapisan utama:
1. **Layer 1: Ingestion** (Data mentah masuk ke Apache Kafka)
2. **Layer 2: Normalization** (Penyeragaman struktur data)
3. **Layer 3: CMDB Enrichment** (Pencocokan data metrik dengan CMDB Redis/iTop)
4. **Layer 4: Indexing & Storage** (Penyimpanan akhir ke Elasticsearch via NiFi)
5. **Layer 5: Visualization & Alerting** (Dasbor Kibana & Notifikasi Telegram)

---

## Persiapan Simulasi
Sebelum memulai pengujian, gunakan skrip *generator* bawaan untuk menembakkan data tiruan (dummy) ke dalam pipeline. Skrip ini akan membuat data sensor *server* fiktif.

Jalankan perintah ini di satu terminal (Terminal Ingestion):
```bash
python3 /home/infra/dcim_metrics_project/scripts/tests/dcim_test_payload_generator.py \
  --rate 1 --duration 5 --topic dcim.raw.server
```
*Output yang diharapkan: Skrip akan mengirimkan 5 pesan ke topik `dcim.raw.server` dengan nama host `TEST-SRV-XXX` dan serial number `TEST-SN-XXX`.*

---

## Detail Pengujian per Layer

### Layer 1: Ingestion (Apache Kafka - Raw Topic)
**Tujuan:** Memastikan data mentah dari perangkat/skrip produsen berhasil diterima oleh *Message Broker* (Kafka).

**Cara Verifikasi:**
Gunakan Kafka Console Consumer untuk menyadap (sniffing) topik secara *real-time*.
```bash
/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic dcim.raw.server --max-messages 5
```
> [!TIP]
> Jika data muncul dalam format JSON mentah (seperti `"reading_celsius": 35`), maka Kafka berfungsi normal dan siap meneruskan data ke *Normalizer*.

### Layer 2: Normalization (Python Normalizer Service)
**Tujuan:** Memastikan *Normalizer* mengambil data mentah, merapikan field menjadi format ECS (Elastic Common Schema), dan mempublikasikannya kembali.

**Cara Verifikasi (Log Service):**
```bash
journalctl -u dcim-normalizer.service -n 50 -f
```
*Output yang diharapkan: Terlihat log proses konversi field `reading_celsius` menjadi `dcim_metrics.raw_fields_reading_celsius`.*

**Cara Verifikasi (Kafka Output Topic):**
Lihat hasil normalisasi yang diteruskan ke topik berikutnya:
```bash
/opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic dcim.normalized.events --max-messages 5
```

### Layer 3: CMDB Enrichment (API & Redis Cache)
**Tujuan:** Memastikan sistem mencoba mencocokkan *Serial Number* (SN) alat ke database aset (iTop CMDB) yang disimpan di Redis.

**Cara Verifikasi (API Log):**
```bash
journalctl -u dcim-enrichment-api.service -f
```
*Output yang diharapkan: Anda akan melihat permintaan `GET /enrich/TEST-SN-001`. Karena ini adalah data tiruan, API akan mengembalikan status `NOT_IN_CMDB`.*

**Cara Verifikasi (Manual Redis Check):**
Untuk menguji aset asli, periksa apakah aset ada di dalam Cache Redis:
```bash
redis-cli -h 10.70.0.56 -p 6379 GET "asset:sn:TEST-SN-001"
```
> [!NOTE]
> Jika sistem menghasilkan `NOT_IN_CMDB` untuk alat asli (bukan simulasi), pastikan `dcim-itop-redis-sync.timer` berjalan untuk menarik data baru dari iTop.

### Layer 4: Indexing & Storage (Elasticsearch)
**Tujuan:** Memastikan bahwa NiFi atau Kafka Connect sukses menelan (*ingest*) data dari `dcim.normalized.events` dan menuliskannya secara permanen ke Elasticsearch.

**Cara Verifikasi (Elasticsearch Query):**
Tembak REST API Elasticsearch untuk mencari data dummy yang baru saja disuntikkan:
```bash
curl -s -X POST "https://10.70.0.56:9200/dcim-metrics-unified-*/_search" \
  -H 'Content-Type: application/json' \
  -u elastic:C+H+pFb*aIAqWcOo-X8q -k \
  -d '{
        "size": 5,
        "query": {
          "match": {
            "tag.serial_number": "TEST-SN-001"
          }
        }
      }' | jq '.hits.hits[]._source'
```
*Output yang diharapkan: Dokumen JSON utuh yang menampilkan kolom pengayaan seperti `tag.enrichment_status: "NOT_IN_CMDB"`.*

### Layer 5: Visualization & Alerting (Kibana & Telegram)
**Tujuan:** Membuktikan data dapat dilihat secara visual dan dievaluasi oleh sistem peringatan (*watcher*).

**Cara Verifikasi Visual:**
1. Buka Dasbor Kibana DCIM (http://10.70.0.56:5601/app/dashboards).
2. Gunakan filter KQL di panel atas: `tag.serial_number: "TEST-SN-*"`
3. Dasbor harus menampilkan metrik dan tabel berisi data tersebut.

**Cara Verifikasi Alerting (Log):**
Alert `NOT_IN_CMDB` yang Anda lihat sebelumnya di Telegram dibangkitkan oleh Kibana atau skrip alerter kustom. Periksa log alerter:
```bash
journalctl -u dcim-telegram-alerter.service -n 50
```

---

## Pembersihan Data Simulasi (Cleanup)
Data dummy yang disuntikkan akan tersimpan secara persisten di Elasticsearch. Untuk menjaga agar laporan produksi tetap bersih, disarankan untuk menghapus data dummy setelah proses pengujian selesai:

```bash
curl -s -X POST "https://10.70.0.56:9200/dcim-metrics-unified-*/_delete_by_query" \
  -H 'Content-Type: application/json' \
  -u elastic:C+H+pFb*aIAqWcOo-X8q -k \
  -d '{
        "query": {
          "wildcard": {
            "tag.hostname.keyword": "TEST-SRV-*"
          }
        }
      }'
```
*Output yang diharapkan: JSON response dengan `"deleted": 5` (atau sebanyak jumlah data simulasi yang Anda kirim).*
