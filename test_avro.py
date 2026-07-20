import sys
import json
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

sys.path.append("/home/infra/dcim_metrics_project")
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA

schema_registry_client = SchemaRegistryClient({'url': 'http://localhost:8081'})
avro_deserializer = AvroDeserializer(schema_registry_client, ENRICHED_EVENT_SCHEMA)

consumer = Consumer({
    'bootstrap.servers': 'localhost:9094',
    'group.id': 'test-group',
    'auto.offset.reset': 'latest',
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False
})
consumer.subscribe(['dcim.enriched.events'])

msgs = []
while len(msgs) < 3:
    msg = consumer.poll(1.0)
    if msg is None: continue
    if msg.error(): continue
    val = avro_deserializer(msg.value(), SerializationContext('dcim.enriched.events', MessageField.VALUE))
    msgs.append(val)

print(json.dumps(msgs, indent=2))
consumer.close()
