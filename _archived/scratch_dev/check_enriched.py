import sys
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

sys.path.append("/home/infra/dcim_metrics_project")
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA

schema_registry_conf = {'url': 'http://localhost:8081'}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)
avro_deserializer = AvroDeserializer(schema_registry_client, ENRICHED_EVENT_SCHEMA)

consumer_conf = {
    'bootstrap.servers': 'localhost:9094',
    'group.id': 'check-enriched-temp',
    'auto.offset.reset': 'latest',
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False
}

c = Consumer(consumer_conf)
c.subscribe(['dcim.enriched.events'])

print("Waiting for messages...")
count = 0
while count < 5:
    msg = c.poll(5.0)
    if msg is None: continue
    if msg.error(): continue
    ctx = SerializationContext("dcim.enriched.events", MessageField.VALUE)
    val = avro_deserializer(msg.value(), ctx)
    print(f"[{count}] event_time={val.get('event_time')} metric={val.get('metric_name')} type={val.get('device_type')}")
    count += 1
c.close()
