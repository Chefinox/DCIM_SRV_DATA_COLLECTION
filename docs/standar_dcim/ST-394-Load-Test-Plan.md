# ST-394 End-to-End Integration Testing & Load Verification

## Objective
Validasi requirement beban data pipeline mencapai sustained `430 events per second (eps)` dengan latency persentil 99 (p99) di bawah 1 detik, sesuai panduan `block2-data-ingestion-integration.md`.

## Execution Tools
- **Locust** (`tests/load_testing/locustfile.py`): Digunakan untuk melakukan *swarm* traffic ke pintu masuk (entrypoint) pipeline NiFi. Skrip telah dibekali dua task: valid metric payloads (75% probability) dan invalid payloads untuk menguji fitur DLQ Validation Engine.

## Expected Outcomes
1. **Throughput (430 EPS):** Elasticsearch dan TimescaleDB dapat menerima sinkronisasi rate pada speed 430 EPS tanpa menaikkan DLQ delay atau Timeout.
2. **Latency (p99 < 1s):** Dashboard Grafana akan memperlihatkan waktu proses dari ujung-ke-ujung (NiFi hingga output storage) berada dalam rentang <1000 milisecond.
3. **Data Quality Integrity:** Event dengan anomali struktur dan *out-of-bounds* (seperti `cpu_usage: 150`) otomatis akan ditarik oleh rute Dead Letter Queue (`parse-failure`/`enrichment-failure`).
