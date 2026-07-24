import json
from kafka import KafkaConsumer
consumer = KafkaConsumer('dcim.analytics.metrics', bootstrap_servers='localhost:9092', auto_offset_reset='latest', consumer_timeout_ms=5000, security_protocol='SSL', ssl_cafile='/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem', ssl_check_hostname=False)
for msg in consumer:
    print(json.loads(msg.value.decode('utf-8')))
    break
