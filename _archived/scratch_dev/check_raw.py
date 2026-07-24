from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'dcim.raw.network.snmp', 'dcim.raw.hardware.server', 'dcim.raw.power.ups',
    bootstrap_servers='localhost:9094',
    group_id='check-raw-temp-1',
    auto_offset_reset='latest',
    consumer_timeout_ms=5000,
    security_protocol='SSL',
    ssl_cafile='/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    ssl_check_hostname=False
)

print("Waiting for RAW messages...")
for msg in consumer:
    print(f"Topic: {msg.topic}, ts={msg.timestamp}")
print("Done.")
