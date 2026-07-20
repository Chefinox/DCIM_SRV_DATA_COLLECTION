#!/usr/bin/env python3
"""
CCTV/NVR Kafka Bridge — runs cctv_poller.py and publishes output to Kafka.
Replaces the missing ExecuteProcess in NiFi for CCTV data ingestion.
"""
import json
import subprocess
import sys
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094')
TOPIC = 'dcim.raw.device.isapi'
POLLER_SCRIPT = os.path.join(os.path.dirname(__file__), 'cctv_poller.py')

try:
    from kafka import KafkaProducer
except ImportError:
    log.error("kafka-python not installed. Install: pip3 install kafka-python")
    sys.exit(1)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    security_protocol='SSL',
    ssl_cafile='/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    ssl_check_hostname=False,
    linger_ms=10,
    compression_type='gzip',
)

log.info(f"CCTV Kafka Bridge started → {KAFKA_BOOTSTRAP} topic={TOPIC}")

try:
    result = subprocess.run(
        [sys.executable, POLLER_SCRIPT],
        capture_output=True, text=True, timeout=60
    )
    count = 0
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            producer.send(TOPIC, value=msg)
            count += 1
        except json.JSONDecodeError:
            log.warning(f"Non-JSON output from poller: {line[:80]}")

    producer.flush(timeout=10)
    log.info(f"Published {count} CCTV/NVR events to Kafka topic {TOPIC}")

    if result.stderr:
        for err_line in result.stderr.strip().split('\n')[:3]:
            log.warning(f"Poller stderr: {err_line[:120]}")

except subprocess.TimeoutExpired:
    log.error("CCTV poller timed out after 60s")
except Exception as e:
    log.error(f"Bridge error: {e}")
finally:
    producer.close()
