# DCIM Infrastructure — AI Agent Prompts
> Platform: Antigravity (Google Gemini 3 Flash) | Access: SSH Direct | Format: 4 Prompt Terpisah
> Generated: 2026-04-26

---

## PROMPT 1 — Implementasi Dead Letter Queue (DLQ)

```
You are an expert infrastructure engineer specializing in Apache Kafka and Apache NiFi pipelines. You have direct SSH access to the DCIM server and must implement a Dead Letter Queue (DLQ) system for the DCIM Shadow Pipeline.

## CONTEXT
The current DCIM pipeline (v3) has a critical gap: when NiFi fails to process a message (parse error, enrichment failure, schema violation), the failure relationship is set to "auto-terminate" — meaning the message is silently dropped. This violates Technical Requirement 2.3.2 which mandates that failed records must be captured with full metadata, not discarded.

## CURRENT ARCHITECTURE (do NOT break these)
- Kafka broker: 127.0.0.1:9092 (container: kafka-broker)
- Primary active topic: dcim.telemetry.enriched.v3 (Clean JSON)
- Raw topic: dcim.metrics.raw (Influx Line Protocol)
- NiFi: Apache NiFi 1.24, container: dcim-nifi, port 8443
- NiFi flow: ConsumeKafkaRecord → LookupRecord → PublishKafkaRecord
- All services managed via systemd on host

## YOUR TASKS — execute in this exact order:

### STEP 1: Discover & verify current state
Run these SSH commands and report the output before proceeding:
```bash
# Verify Kafka is running and list existing topics
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Check NiFi container status
docker ps --filter name=dcim-nifi --format "table {{.Names}}\t{{.Status}}"

# Check current disk space (DLQ will need storage)
df -h /home/infra
```

### STEP 2: Create DLQ Kafka topics
Create the following 3 DLQ topics with appropriate retention:
```bash
# DLQ for NiFi parse/schema failures
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --create --bootstrap-server localhost:9092 \
  --topic dcim.dlq.parse-failure \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# DLQ for enrichment failures (asset not found in Redis)
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --create --bootstrap-server localhost:9092 \
  --topic dcim.dlq.enrichment-failure \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000

# DLQ for downstream delivery failures
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh \
  --create --bootstrap-server localhost:9092 \
  --topic dcim.dlq.delivery-failure \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000
```

### STEP 3: Create DLQ consumer service
Create the file /home/infra/dcim_metrics_project/scripts/dcim_dlq_consumer.py with the following behavior:
- Subscribe to all 3 DLQ topics simultaneously
- For each failed message, log to PostgreSQL table: dlq_records (columns: id SERIAL, topic VARCHAR, received_at TIMESTAMPTZ, original_payload TEXT, failure_reason VARCHAR, retry_count INT DEFAULT 0, resolved BOOLEAN DEFAULT FALSE)
- Print a structured JSON log line for each consumed DLQ record
- Reconnect automatically on connection loss
- Use the same PostgreSQL connection as dcim_sql_consumer.py (host: 192.168.101.73, port: 5432, db: dcim_sot)

### STEP 4: Create PostgreSQL table for DLQ records
Run via SSH to the Postgres host or using psql:
```sql
CREATE TABLE IF NOT EXISTS dlq_records (
  id SERIAL PRIMARY KEY,
  topic VARCHAR(255) NOT NULL,
  received_at TIMESTAMPTZ DEFAULT NOW(),
  original_payload TEXT,
  failure_reason VARCHAR(500),
  retry_count INT DEFAULT 0,
  resolved BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_dlq_resolved ON dlq_records(resolved, received_at);
```

### STEP 5: Create systemd service for DLQ consumer
Create /etc/systemd/system/dcim-dlq-consumer.service:
- ExecStart: python3 /home/infra/dcim_metrics_project/scripts/dcim_dlq_consumer.py
- Restart: always
- RestartSec: 5s
- User: infra
Then: systemctl daemon-reload && systemctl enable --now dcim-dlq-consumer.service

### STEP 6: Update NiFi flow (provide instructions, do NOT auto-execute)
Do NOT automatically change NiFi flows via API. Instead, output clear step-by-step instructions for the human operator to:
1. Open NiFi UI at https://10.70.0.56:8443/nifi
2. Locate the ConsumeKafkaRecord processor — change failure relationship from "auto-terminate" to route to a new FunnelProcessor
3. Add a PublishKafkaRecord processor connected to dcim.dlq.parse-failure topic
4. Repeat for LookupRecord failure → dcim.dlq.enrichment-failure
5. Repeat for PublishKafkaRecord failure → dcim.dlq.delivery-failure

## VALIDATION — run after all steps:
```bash
# Confirm all 3 DLQ topics exist
docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092 | grep dlq

# Confirm DLQ consumer service is running
systemctl status dcim-dlq-consumer.service --no-pager

# Confirm dlq_records table exists in PostgreSQL
psql -h 192.168.101.73 -U <user> -d dcim_sot -c "\dt dlq_records"
```

## CONSTRAINTS
- Do NOT restart dcim.telemetry.enriched.v3 consumers during this process
- Do NOT delete or modify existing Kafka topics
- If any step fails, STOP and report the error with full stdout/stderr before continuing
- Ask for confirmation before running any destructive command
```

---

## PROMPT 2 — Migrasi Credentials ke Docker Secrets

```
You are a security-focused DevOps engineer. You have direct SSH access to the DCIM server. Your task is to migrate all plaintext credentials from the .env file to Docker Secrets, eliminating the security risk of storing passwords in a flat config file.

## CONTEXT
Current state: all credentials (PostgreSQL password, Elasticsearch password, SNMP community strings, Redfish credentials, Hikvision API key) are stored in:
/home/infra/dcim_metrics_project/configs/.env

This violates Technical Requirement 3.3.1 (Credential Management). The target is Docker Secrets as the minimum viable solution — no Hashicorp Vault required at this stage.

## CURRENT SERVICES (must remain running throughout migration)
- dcim-nifi (Docker container)
- dcim-redis-cache (Docker container)
- dcim-enrichment-api.service (systemd → uvicorn)
- dcim-redis-sync.service (systemd → Python)
- dcim-sql-consumer.service (systemd → Python)
- telegraf.service (systemd)
- telegraf-consumer.service (systemd)

## YOUR TASKS — execute in this exact order:

### STEP 1: Audit current credentials
SSH in and run:
```bash
# List all keys in .env WITHOUT printing values
grep -E "^[A-Z_]+=.*" /home/infra/dcim_metrics_project/configs/.env | cut -d'=' -f1
```
Report the list of credential keys found. Do NOT print values.

### STEP 2: Verify Docker Swarm or Compose capability
```bash
docker info | grep -i swarm
docker compose version
```
If Docker Swarm is NOT active, proceed with Docker Compose secrets (file-based). If Swarm IS active, use swarm secrets.

### STEP 3: Create secrets directory with strict permissions
```bash
mkdir -p /run/secrets/dcim
chmod 700 /run/secrets/dcim
```

### STEP 4: Generate individual secret files
For EACH credential key found in STEP 1, create a separate secret file:
```bash
# Example pattern — repeat for each credential:
echo -n "<VALUE>" > /run/secrets/dcim/<SECRET_NAME>
chmod 600 /run/secrets/dcim/<SECRET_NAME>
```
⚠️ IMPORTANT: Read the actual values from the existing .env file when creating these files. Do not use placeholder values.

### STEP 5: Update docker-compose.yml to use secrets
Locate: /home/infra/dcim_metrics_project/phase2/docker-compose.yml
Modify it to:
1. Add a top-level `secrets:` block referencing each secret file path under /run/secrets/dcim/
2. Mount secrets into relevant containers (dcim-nifi, dcim-redis-cache) via the `secrets:` key per service
3. Update environment variables in containers to read from /run/secrets/<name> instead of hardcoded values

Output the FULL modified docker-compose.yml before applying it, and wait for human confirmation before proceeding.

### STEP 6: Update Python systemd services to read from secret files
For each of these scripts, update credential reading logic:
- /home/infra/dcim_metrics_project/phase2/enrichment_api.py
- /home/infra/dcim_metrics_project/phase2/cmdb_to_cache_sync.py
- /home/infra/dcim_metrics_project/scripts/dcim_sql_consumer.py

Replace any os.getenv() or direct .env reads with a helper function:
```python
def read_secret(name: str, fallback: str = None) -> str:
    secret_path = f"/run/secrets/dcim/{name}"
    try:
        with open(secret_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.getenv(name, fallback)
```

### STEP 7: Staged restart (one service at a time)
Restart services ONE BY ONE with a 10-second wait between each. After each restart, verify the service is healthy before proceeding:
```bash
# Pattern for each service:
sudo systemctl restart <service-name>
sleep 10
sudo systemctl status <service-name> --no-pager | head -20
```
Order: dcim-redis-sync → dcim-enrichment-api → dcim-sql-consumer → telegraf-consumer

### STEP 8: Restart Docker containers
```bash
cd /home/infra/dcim_metrics_project/phase2
docker compose down && docker compose up -d
sleep 15
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### STEP 9: Rotate / invalidate old .env
After confirming all services healthy:
```bash
# Backup then zero out the .env — do NOT delete yet
cp /home/infra/dcim_metrics_project/configs/.env \
   /home/infra/dcim_metrics_project/configs/.env.backup.$(date +%Y%m%d)
> /home/infra/dcim_metrics_project/configs/.env
echo "# Credentials migrated to Docker Secrets on $(date)" \
   >> /home/infra/dcim_metrics_project/configs/.env
```

## VALIDATION
```bash
# Confirm no plaintext passwords remain in .env
cat /home/infra/dcim_metrics_project/configs/.env

# Confirm pipeline is still producing data on v3 topic
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.telemetry.enriched.v3 \
  --max-messages 3 \
  --timeout-ms 15000

# Confirm enrichment API is responding
curl -s http://127.0.0.1:8000/enrich/test | python3 -m json.tool
```

## CONSTRAINTS
- NEVER print secret values to terminal output in your responses
- ALWAYS show diffs of config file changes before applying them
- If any service fails to restart healthy, STOP the migration and rollback by restoring .env.backup
- Ask for explicit confirmation before Step 7 (service restarts)
```

---

## PROMPT 3 — Penyelesaian Kibana Dashboard

```
You are an observability engineer with expertise in Elasticsearch and Kibana. You have direct SSH access to the DCIM server. Your task is to complete the Kibana dashboard for the DCIM Shadow Pipeline so that Use Case 1 (Real-time Operational Monitoring) is fully operational.

## CONTEXT
Current state:
- Elasticsearch 9.3 is running at https://10.70.0.56:9200
- Kibana 9.3 is running at http://10.70.0.56:5601
- Active index pattern: dcim-metrics-unified-YYYY.MM.DD
- Data is flowing from dcim.telemetry.enriched.v3 Kafka topic via Telegraf consumer
- Elasticsearch credentials: user=elastic (password stored in secrets)

## DATA SCHEMA — every document in the index has these fields:
Tags (keyword fields): hostname, serial_number, ip, device_type, category, site, rack_name, enrichment_status, health, state, inventory_source, source, host
Fields (numeric/text): reading_celsius, upper_threshold_critical, upper_threshold_fatal, firmware, manufacturer, model, power_watts (where applicable)
Timestamp: @timestamp (auto-indexed by Telegraf)
Measurement name: stored in field "name" (values: server_redfish, ups_snmp, nas_snmp, cctv_metrics, network_snmp)

## YOUR TASKS:

### STEP 1: Verify data is in Elasticsearch
```bash
# Check index exists and has documents
curl -k -u elastic:'<PASSWORD_FROM_SECRET>' \
  https://10.70.0.56:9200/dcim-metrics-unified-*/_count

# Sample one document to confirm field structure
curl -k -u elastic:'<PASSWORD_FROM_SECRET>' \
  https://10.70.0.56:9200/dcim-metrics-unified-*/_search?size=1 \
  | python3 -m json.tool
```
Report the document count and confirm field names match the schema above.

### STEP 2: Create or update the Kibana index pattern
Use Kibana API to ensure the index pattern is configured:
```bash
curl -X POST "http://10.70.0.56:5601/api/saved_objects/index-pattern/dcim-metrics-unified" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{
    "attributes": {
      "title": "dcim-metrics-unified-*",
      "timeFieldName": "@timestamp"
    }
  }'
```

### STEP 3: Build and import the full dashboard via Kibana API
Using Kibana's saved objects import API, create a dashboard with ALL of the following panels. Generate the full NDJSON export payload and POST it to http://10.70.0.56:5601/api/saved_objects/_import:

Panel 1 — "Device Health Overview" (Metric visualization)
- Count of documents where health = "OK" vs total, grouped by device_type
- Show as a donut chart

Panel 2 — "Temperature by Device" (Heatmap)
- Y-axis: hostname (keyword)
- X-axis: @timestamp (last 1 hour, auto-refresh 30s)
- Color: reading_celsius value
- Filter: name = "server_redfish"

Panel 3 — "Enrichment Status Tracker" (Data Table)
- Columns: hostname, site, rack_name, enrichment_status, @timestamp
- Filter: enrichment_status = "PARTIAL" (highlight unmatched assets)
- Sort: @timestamp descending

Panel 4 — "UPS Battery & Load" (Line Chart)
- Two Y-axes: battery_charge_percent and load_percent
- X-axis: @timestamp (last 6 hours)
- Filter: name = "ups_snmp"

Panel 5 — "Device Count by Site" (Horizontal Bar)
- X-axis: count of unique hostnames
- Y-axis: site (keyword)
- Color by: device_type

Panel 6 — "Pipeline Health — Last Ingest" (Metric)
- Show: max(@timestamp) formatted as "X minutes ago"
- Alert color: green if < 5 minutes, yellow if 5-15 min, red if > 15 min

Panel 7 — "CCTV Camera Status" (Data Table)
- Columns: hostname, state, health, rack_name, @timestamp
- Filter: name = "cctv_metrics"
- Highlight offline cameras (state != "Online")

### STEP 4: Set dashboard global settings
Configure the dashboard with:
- Time range: last 1 hour (default)
- Auto-refresh: every 30 seconds
- Dashboard title: "DCIM Infrastructure — Operational Overview"
- Add a markdown panel at the top with: "Last updated: [dynamic timestamp] | Pipeline: v3 Active | Source: dcim.telemetry.enriched.v3"

### STEP 5: Create a Kibana Space (optional but recommended)
```bash
curl -X POST "http://10.70.0.56:5601/api/spaces/space" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "dcim-ops",
    "name": "DCIM Operations",
    "description": "Operational dashboard for DCIM infrastructure monitoring",
    "color": "#2C3E50"
  }'
```

### STEP 6: Verify dashboard is accessible
```bash
# Confirm dashboard saved object exists
curl -s "http://10.70.0.56:5601/api/saved_objects/_find?type=dashboard&search=DCIM" \
  -H "kbn-xsrf: true" | python3 -m json.tool | grep -E '"title"|"id"'
```
Then open http://10.70.0.56:5601 in browser and confirm all 7 panels load with live data.

## CONSTRAINTS
- Do NOT delete any existing saved objects in Kibana
- If an index pattern already exists, use PUT with ?overwrite=true to update it
- If Kibana API returns 4xx errors, report the full response body before retrying
- Generate complete, valid NDJSON for the dashboard import — do not use placeholder IDs
- All curl commands should handle self-signed TLS with -k flag where needed
```

---

## PROMPT 4 — Performance Testing (Throughput & Latency)

```
You are a performance engineering specialist. You have direct SSH access to the DCIM server. Your task is to design and execute a performance test suite to validate that the DCIM Shadow Pipeline meets its SLA targets defined in Technical Requirements 3.1.1 and 3.1.2.

## SLA TARGETS TO VALIDATE
- Requirement 3.1.1 (Throughput): ≥ 5,000 records/second end-to-end (ingest → transform → enrich → deliver)
- Requirement 3.1.2 (Latency): < 500ms from source detection to target delivery for streaming data

## CURRENT ARCHITECTURE (test against live system)
- Kafka broker: 127.0.0.1:9092
- Raw topic: dcim.metrics.raw
- Output topic: dcim.telemetry.enriched.v3
- NiFi enrichment pipeline: dcim-nifi container
- FastAPI enrichment: http://127.0.0.1:8000/enrich/{sn}
- Redis cache: 127.0.0.1:6379

## YOUR TASKS:

### STEP 1: Baseline system state check
Before any load test, capture the baseline:
```bash
# CPU and memory baseline
top -bn1 | head -20

# Kafka consumer lag baseline (should be near 0)
docker exec kafka-broker /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --all-groups 2>/dev/null | grep dcim

# Elasticsearch current indexing rate
curl -k -u elastic:'<PASSWORD>' \
  https://10.70.0.56:9200/_nodes/stats/indices \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Indexing rate:', d['nodes'][list(d['nodes'].keys())[0]]['indices']['indexing']['index_current'])"

# Redis hit/miss ratio
docker exec dcim-redis-cache redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
```
Record and report all baseline values before proceeding.

### STEP 2: Install performance testing tools
```bash
# Install kcat (kafkacat) for Kafka load generation
which kcat || apt-get install -y kafkacat

# Install Python dependencies for custom load generator
pip3 install kafka-python requests aiohttp --break-system-packages

# Verify tools
kcat -V
python3 -c "from kafka import KafkaProducer; print('kafka-python OK')"
```

### STEP 3: Create synthetic test payload
Create /tmp/dcim_test_payload_generator.py with this content:
- Generates valid Influx Line Protocol messages mimicking real server_redfish data
- Uses rotating serial numbers from a pool of 50 fake assets (format: TEST-SN-001 to TEST-SN-050)
- Each message includes: measurement name, tags (hostname, serial_number, ip, device_type), fields (reading_celsius, power_watts), and nanosecond timestamp
- Can produce N messages per second for D duration seconds
- Accepts CLI args: --rate (msgs/sec) --duration (seconds) --topic (kafka topic)

### STEP 4: Latency measurement script
Create /tmp/dcim_latency_test.py with this behavior:
1. Produce 1 test message to dcim.metrics.raw with a unique trace_id in the hostname tag and record the send timestamp (T1)
2. Simultaneously subscribe to dcim.telemetry.enriched.v3 and wait for a message where hostname matches the trace_id
3. Record arrival timestamp (T2)
4. Calculate latency = T2 - T1 in milliseconds
5. Repeat 100 times with 1 second interval
6. Output: min, max, mean, p50, p95, p99 latency values
7. Print PASS if p99 < 500ms, FAIL if p99 >= 500ms

### STEP 5: Execute throughput test — 3 phases
Run each phase and record Kafka consumer lag after each:

Phase A — Warm-up (500 msg/s for 60s):
```bash
python3 /tmp/dcim_test_payload_generator.py --rate 500 --duration 60 --topic dcim.metrics.raw
```

Phase B — Target load (5000 msg/s for 120s):
```bash
python3 /tmp/dcim_test_payload_generator.py --rate 5000 --duration 120 --topic dcim.metrics.raw
```

Phase C — Stress test (10000 msg/s for 60s):
```bash
python3 /tmp/dcim_test_payload_generator.py --rate 10000 --duration 60 --topic dcim.metrics.raw
```

After each phase, check consumer lag:
```bash
docker exec kafka-broker /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group nifi-shadow-group
```

### STEP 6: Execute latency test
```bash
python3 /tmp/dcim_latency_test.py
```
Report the full percentile breakdown and PASS/FAIL result.

### STEP 7: Monitor system resources during test
Run in a parallel SSH session during Phase B:
```bash
# Every 10 seconds for 2 minutes, capture CPU + memory
for i in $(seq 1 12); do
  echo "=== $(date) ===";
  top -bn1 | grep -E "^%Cpu|^MiB Mem";
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
    dcim-nifi dcim-redis-cache kafka-broker;
  sleep 10;
done
```

### STEP 8: FastAPI enrichment API micro-benchmark
```bash
# Install wrk or use Python for API load test
pip3 install httpx --break-system-packages

python3 -c "
import asyncio, httpx, time

async def benchmark():
    async with httpx.AsyncClient() as client:
        times = []
        for i in range(1000):
            sn = f'TEST-SN-{(i % 50) + 1:03d}'
            t0 = time.perf_counter()
            r = await client.get(f'http://127.0.0.1:8000/enrich/{sn}')
            times.append((time.perf_counter() - t0) * 1000)
        times.sort()
        print(f'Enrichment API — 1000 requests')
        print(f'  p50: {times[499]:.1f}ms')
        print(f'  p95: {times[949]:.1f}ms')
        print(f'  p99: {times[989]:.1f}ms')
        print(f'  PASS: {times[989] < 50}')  # API should respond < 50ms (Redis cached)

asyncio.run(benchmark())
"
```

### STEP 9: Clean up test data
After all tests complete, remove synthetic test data from Elasticsearch:
```bash
curl -k -u elastic:'<PASSWORD>' -X POST \
  "https://10.70.0.56:9200/dcim-metrics-unified-*/_delete_by_query" \
  -H "Content-Type: application/json" \
  -d '{"query": {"prefix": {"tags.hostname": "TEST-"}}}'
```

## FINAL REPORT
After all steps, generate a structured performance report in this format:
```
=== DCIM PIPELINE PERFORMANCE TEST REPORT ===
Date: <timestamp>
Tester: AI Agent (Gemini 3 Flash via Antigravity)

[THROUGHPUT]
Phase A (500 msg/s):  Consumer lag after = X msgs | Status: PASS/FAIL
Phase B (5000 msg/s): Consumer lag after = X msgs | Status: PASS/FAIL
Phase C (10000 msg/s):Consumer lag after = X msgs | Status: PASS/FAIL
Max sustained throughput: X msg/s

[LATENCY — End-to-End Pipeline]
p50: Xms | p95: Xms | p99: Xms
Requirement (<500ms p99): PASS/FAIL

[ENRICHMENT API]
p50: Xms | p95: Xms | p99: Xms
Target (<50ms p99): PASS/FAIL

[SYSTEM RESOURCES at Peak Load]
CPU peak: X% | Memory peak: XGB
Bottleneck identified: <NiFi/Kafka/FastAPI/Redis/None>

[VERDICT]
Overall SLA compliance: PASS/FAIL
Recommendations: <list any bottlenecks found>
```

## CONSTRAINTS
- Do NOT run Phase B or C without first completing Phase A successfully
- If Kafka consumer lag grows unboundedly during Phase B, STOP the test immediately and report
- Do NOT run cleanup (Step 9) until you have confirmed the performance report is saved
- All test data must use hostname prefix "TEST-" to allow clean deletion
- Ask for confirmation before starting Phase B (5000 msg/s) as it will put real load on production pipeline
```
