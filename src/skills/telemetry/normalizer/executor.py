import os
import json
import uuid
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer

# Lokasi config tetap merujuk ke folder config utama
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
    hostname_raw = (
        tags.get("hostname") or 
        fields.get("system_name") or 
        fields.get("sysName") or 
        "Unknown_Host"
    )
    hostname = str(hostname_raw).strip()
    serial_number = (
        tags.get("serial_number") or
        fields.get("serial_number") or
        fields.get("upsSerial") or
        fields.get("sysSerial") or
        "NO_IDENTIFIER"
    )
    metric_name, metric_value, metric_unit, severity = resolve_metric(raw_message)
    device_type = resolve_device_type(raw_message, source_topic)

    if device_type in ("cctv", "nvr"):
        tag_model = tags.get("model")
        if tag_model and str(tag_model).strip().lower() not in ("", "unknown", "null", "none"):
            fields.setdefault("model", tag_model)
        tag_firmware = tags.get("firmware") or tags.get("firmwareVersion")
        if tag_firmware and str(tag_firmware).strip().lower() not in ("", "unknown", "null", "none"):
            fields.setdefault("firmware", tag_firmware)
        if tag_model and str(tag_model).strip().upper().startswith("DS-"):
            fields.setdefault("manufacturer", "Hikvision")
    
    if device_type == "ups":
        try:
            curr_load = int(fields.get("output_load") or 0)
            if curr_load == 0:
                l1 = int(fields.get("output_load_L1") or 0)
                l2 = int(fields.get("output_load_L2") or 0)
                l3 = int(fields.get("output_load_L3") or 0)
                max_load = max(l1, l2, l3)
                if max_load > 0:
                    fields["output_load"] = max_load
                    if metric_name == "output_load":
                        metric_value = max_load
        except Exception:
            pass
            
    # Calculate Memory Usage Percentage for CCTV/NVR
    if "memoryUsage" in fields and "memoryAvailable" in fields:
        try:
            used = float(fields["memoryUsage"])
            avail = float(fields["memoryAvailable"])
            total = used + avail
            if total > 0:
                fields["memoryUsagePct"] = round((used / total) * 100, 2)
                fields["memoryTotal"] = round(total, 2)
                fields["memoryUsage"] = round(used, 2)
                fields["memoryAvailable"] = round(avail, 2)
        except Exception:
            pass
            
    # Calculate Volume Usage Percentage for NAS
    vol_used = fields.get("volumeUsedBytes") or fields.get("volumes_used_bytes") or fields.get("used_bytes")
    vol_total = fields.get("volumeTotalBytes") or fields.get("volumes_total_bytes") or fields.get("total_bytes")
    vol_status = fields.get("volumeStatus") or fields.get("status_val") or fields.get("status")

    if vol_used is not None and vol_total is not None:
        try:
            used_bytes = float(vol_used)
            total_bytes = float(vol_total)
            if total_bytes > 0:
                fields["volumeUsagePct"] = round((used_bytes / total_bytes) * 100, 2)
                fields["volumeUsedGB"] = round(used_bytes / (1024 ** 3), 2)
                fields["volumeTotalTB"] = round(total_bytes / (1024 ** 4), 2)
                
            # Unify standard fields for Bar Chart
            fields["volumeTotalBytes"] = total_bytes
            fields["volumeUsedBytes"] = used_bytes
        except Exception:
            pass
            
    # Unify Status if missing
    if "volumeStatus" not in fields and vol_status is not None:
        try:
            status_str = str(vol_status).lower()
            if status_str in ["online", "normal", "1", "ok"]:
                fields["volumeStatus"] = 1
            else:
                fields["volumeStatus"] = int(vol_status)
        except Exception:
            pass
            
    ts = raw_message.get("timestamp")
    event_time = None
    if ts:
        try:
            ts_float = float(ts)
            parsed_ts = ts_float / 1e9 if ts_float > 1e16 else (ts_float / 1e3 if ts_float > 1e11 else ts_float)
            event_time = datetime.fromtimestamp(parsed_ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        except Exception:
            pass
    clean_tags = dict(tags)
    if "host" in clean_tags:
        del clean_tags["host"]
    normalized_event = {
        "event_id": str(uuid.uuid4()),
        "event_time": event_time,
        "timestamp": int(parsed_ts) if 'parsed_ts' in locals() else ts,
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
        "manufacturer": fields.get("manufacturer") or tags.get("manufacturer"),
        "model": fields.get("model") or tags.get("model"),
        "firmware": fields.get("firmware") or fields.get("firmwareVersion") or tags.get("firmware") or tags.get("firmwareVersion"),
        "raw_fields": fields,
        "raw_tags": clean_tags
    }
    return normalized_event

def run():
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
    print("Starting python normalizer service (V3 Logic in V4 Structure)...")
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
    run()
