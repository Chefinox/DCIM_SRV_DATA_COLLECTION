# Configuration Directory

Configuration files for DCIM pipeline components.

## Structure

### telegraf/
Telegraf input configuration files for data collection:
- `servers-redfish.conf` - Server metrics via Redfish HTTPS (5 servers)
- `ups-apc.conf` - UPS metrics via SNMP v3 (1 UPS)
- `nas-snmp.conf` - NAS metrics via SNMP v3 (6 NAS)
- `mikrotik-snmp.conf` - Network metrics via SNMP v2c (5 switches/routers)

**Polling Interval**: 120 seconds (2 minutes) for all devices

### systemd/
Systemd service unit files:
- `dcim-normalizer.service` - Normalization service
- `dcim-enrichment-api.service` - FastAPI enrichment endpoint
- `dcim-redis-sync.service` - Redis cache sync (60s interval)
- `dcim-sql-consumer.service` - PostgreSQL consumer
- `dcim-dlq-consumer.service` - Dead letter queue handler
- `dcim-kafka-es-sync.service` - Kafka to Elasticsearch sync
- `dcim-ralph-sync.service` - Ralph CMDB sync service
- `dcim-ralph-sync.timer` - Timer for Ralph sync

### docker/
Docker Compose configurations:
- `docker-compose.yml` - Kafka, Redis, NiFi containers

### Root Level
- `metric_mapping.json` - Normalization rules (topic → device_type, measurement → device_type)
- `metric_mapping.yaml` - Alternative YAML format
- `.env` - Environment variables (credentials, endpoints)

## Usage

### Telegraf Configs
Configs are loaded by telegraf service:
```bash
sudo systemctl restart telegraf
```

### Systemd Services
Install and enable services:
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dcim-normalizer.service
sudo systemctl start dcim-normalizer.service
```

### Docker Containers
Start containers:
```bash
cd docker/
docker-compose up -d
```

## Important Notes

- **Credentials**: Stored in `.env` file (not in git)
- **Polling Interval**: Standardized to 120s to balance visibility and device load
- **Service Dependencies**: Services depend on Kafka and PostgreSQL being available
