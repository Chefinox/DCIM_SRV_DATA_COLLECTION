import json
import os
from kafka import KafkaConsumer, TopicPartition

KAFKA_BOOTSTRAP_SERVERS = 'localhost:9094'
TOPICS = ['dcim.raw.hardware.server', 'dcim.raw.power.ups', 'dcim.raw.network.snmp', 'dcim.raw.device.isapi', 'dcim.normalized.events', 'dcim.enriched.events', 'dcim.analytics.metrics']

def check_latest_timestamp():
    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        security_protocol='SSL',
        ssl_cafile='/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
        ssl_check_hostname=False,
        value_deserializer=lambda m: m
    )

    for topic in TOPICS:
        partitions = consumer.partitions_for_topic(topic)
        if not partitions:
            print(f"Topic {topic} has no partitions.")
            continue
        
        tps = [TopicPartition(topic, p) for p in partitions]
        consumer.assign(tps)
        consumer.seek_to_end(*tps)
        
        latest_msg = None
        
        for tp in tps:
            end_offset = consumer.position(tp)
            if end_offset > 0:
                consumer.seek(tp, end_offset - 1)
                try:
                    # Poll for the last message
                    msgs = consumer.poll(timeout_ms=2000)
                    if tp in msgs and msgs[tp]:
                        msg = msgs[tp][-1]
                        print(f"Topic {topic} (Part {tp.partition}): Last Msg Offset {msg.offset}, Timestamp {msg.timestamp}")
                except Exception as e:
                    print(f"Error on {topic} part {tp.partition}: {e}")

check_latest_timestamp()
