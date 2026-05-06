import os
import json
import uuid
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer

CONFIG_PATH = "/home/infra/dcim_metrics_project/configs/metric_mapping.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {}

config = load_config()

def resolve_device_type(raw_message, source_topic):
    tags = raw_message.get("tags", {})
    if tags.get("device_type"):
        return tags["device_type"]
    topic_map = config.get("topic_to_device_type", {})
    for topic_prefix, device_type in topic_map.items():
        if source_topic.startswith(topic_prefix):
            return device_type
    measurement_map = config.get("measurement_to_device_type", {})
    return measurement_map.get(raw_message.get("name"), "unknown")

def resolve_metric(raw_message):
    measurement = raw_message.get("name")
    mapping = config.get(measurement, config.get("default", {}))
    metric_name = mapping.get("metric_name", "general_metric")
    metric_field = mapping.get("metric_field")
    metric_unit = mapping.get("metric_unit")
    severity = "info"
    fields = raw_message.get("fields", {})
    metric_value = fields.get(metric_field) if metric_field else None
    severity_field = mapping.get("severity_field")
    if severity_field and severity_field in fields:
        val = str(fields[severity_field])
        severity = mapping.get("severity_map", {}).get(val, "info")
    return metric_name, metric_value, metric_unit, severity

def process_message(raw_message, source_topic):
    tags = raw_message.get("tags", {})
    fields = raw_message.get("fields", {})
    hostname = tags.get("hostname")
    serial_number = (
        tags.get("serial_number") or
        fields.get("upsSerial") or
        fields.get("sysSerial") or
        "NO_IDENTIFIER"
    )
    metric_name, metric_value, metric_unit, severity = resolve_metric(raw_message)
    device_type = resolve_device_type(raw_message, source_topic)
    ts = raw_message.get("timestamp")
    event_time = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00') if ts else None
    clean_tags = dict(tags)
    if "host" in clean_tags:
        del clean_tags["host"]
    normalized_event = {
        "event_id": str(uuid.uuid4()),
        "event_time": event_time,
        "timestamp": ts,
        "source_topic": source_topic,
        "measurement": raw_message.get("name"),
        "device_type": device_type,
        "hostname": hostname,
        "ip": tags.get("ip"),
        "serial_number": serial_number,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_unit": metric_unit,
        "severity": severity,
        "raw_fields": fields,
        "raw_tags": clean_tags
    }
    return normalized_event

def main():
    consumer_conf = {
        'bootstrap.servers': '127.0.0.1:9092',
        'group.id': 'dcim_python_normalizer_group',
        'auto.offset.reset': 'latest'
    }
    producer_conf = {
        'bootstrap.servers': '127.0.0.1:9092'
    }
    consumer = Consumer(consumer_conf)
    producer = Producer(producer_conf)
    consumer.subscribe(['^dcim\.raw\..*'])
    print("Starting python normalizer service (V3 - event_time enabled)...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue
            try:
                raw_data = json.loads(msg.value().decode('utf-8'))
                topic = msg.topic()
                normalized = process_message(raw_data, topic)
                producer.produce(
                    "dcim.normalized.events",
                    value=json.dumps(normalized).encode('utf-8')
                )
                print(f"Processed: {topic} -> {normalized['hostname']} [{normalized['device_type']}]")
                producer.poll(0)
            except Exception as e:
                print(f"Error processing message: {e}")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        producer.flush()

if __name__ == "__main__":
    main()
