import json
import os
import psycopg2
from kafka import KafkaConsumer
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

KAFKA_BROKER = "127.0.0.1:9092"
KAFKA_TOPIC  = "dcim.enriched.events"
DB_CONFIG = {
    "host":     "192.168.101.73",
    "database": "dcim_sot",
    "user":     "sot_admin",
    "password": "Inovasi@0918"
}

RAW_FIELD_MAP = {
    # UPS
    "upsBatteryCapacity":   ("ups_battery_capacity",   int),
    "upsBatteryRuntime":    ("ups_battery_runtime",    int),
    "upsBatteryTemp":       ("ups_battery_temp",       float),
    "upsBatteryStatus":     ("ups_battery_status",     int),
    "upsInputVoltage":      ("ups_input_voltage",      float),
    "upsOutputVoltage":     ("ups_output_voltage",     float),
    "upsOutputLoad":        ("ups_output_load",        int),
    "upsOutputFrequency":   ("ups_output_frequency",   float),
    "upsOutputStatus":      ("ups_output_status",      int),
    "upsSecondsOnBattery":  ("ups_seconds_on_battery", int),
    "upsFirmware":          ("ups_firmware",           str),
    "upsModel":             ("ups_model_snmp",         str),
    "upsSerial":            ("ups_serial_snmp",        str),
    "sysUpTime":            ("ups_sys_uptime",         int),

    # NAS
    "diskID":               ("nas_disk_id",            str),
    "diskModel":            ("nas_disk_model",         str),
    "diskStatus":           ("nas_disk_status",        int),
    "diskTemp":             ("nas_disk_temp",          float),
    "system_temp":          ("nas_system_temp",        float),
    "storageSize":          ("nas_storage_size",       int),
    "storageUsed":          ("nas_storage_used",       int),
    "storage_type":         ("nas_storage_type",       str),
    "storageDescr":         ("nas_storage_descr",      str),

    # Network Switch
    "if_name":              ("net_if_name",            str),
    "ifDescr":              ("net_if_descr",           str),
    "ifOperStatus":         ("net_if_oper_status",     int),
    "if_oper_status":       ("net_if_oper_status",     int),
    "ifAdminStatus":        ("net_if_admin_status",    int),
    "ifSpeed":              ("net_if_speed",           int),
    "ifMtu":                ("net_if_mtu",             int),
    "ifType":               ("net_if_type",            int),
    "if_in_octets":         ("net_if_in_octets",       int),
    "if_out_octets":        ("net_if_out_octets",      int),
    "ifInOctets":           ("net_if_in_octets_32",    int),
    "ifOutOctets":          ("net_if_out_octets_32",   int),
    "ifInUcastPkts":        ("net_if_in_ucast_pkts",   int),
    "ifOutUcastPkts":       ("net_if_out_ucast_pkts",  int),
    "ifInNUcastPkts":       ("net_if_in_nucast_pkts",  int),
    "ifOutNUcastPkts":      ("net_if_out_nucast_pkts", int),
    "ifInErrors":           ("net_if_in_errors",       int),
    "ifOutErrors":          ("net_if_out_errors",      int),
    "ifInDiscards":         ("net_if_in_discards",     int),
    "ifOutDiscards":        ("net_if_out_discards",    int),
    "ifInUnknownProtos":    ("net_if_in_unknown_protos",int),
    "ifPhysAddress":        ("net_if_phys_address",    str),
    "ifLastChange":         ("net_if_last_change",     int),
    "ifOutQLen":            ("net_if_out_qlen",        int),

    # Server Redfish
    "reading_celsius":           ("srv_reading_celsius",          float),
    "upper_threshold_critical":  ("srv_upper_threshold_critical", float),
    "upper_threshold_fatal":     ("srv_upper_threshold_fatal",    float),
    "power_watts":               ("srv_power_watts",              float),

    # CCTV
    "status_online":        ("cctv_status_online",     int),
    "status_text":          ("cctv_status_text",       str),
    "channelCount":         ("cctv_channel_count",     int),
    "recordingStatus":      ("cctv_recording_status",  str),
    "deviceName":           ("cctv_device_name",       str),
}

RAW_TAGS_MAP = {
    "firmware": {
        "server_redfish": "srv_firmware",
        "server":         "srv_firmware",
    },
    "health": {
        "server_redfish": "srv_health",
        "server":         "srv_health",
        "cctv":           "cctv_health",
    },
    "state": {
        "server_redfish": "srv_state",
        "server":         "srv_state",
    },
    "hrStorageIndex": {
        "network_switch": "net_if_index",
        "mikrotik":       "net_if_index",
    },
    "ifIndex": {
        "network_switch": "net_if_index",
        "mikrotik":       "net_if_index",
    },
    "sysDescr": {
        "ups": "ups_sys_descr",
        "nas": "nas_sys_descr",
    }
}

def parse_time(t_str):
    if not t_str: return None
    try:
        return datetime.fromisoformat(t_str.replace('Z', '+00:00'))
    except:
        return None

def process_message(data, cur):
    device_type = data.get('device_type', 'unknown')
    
    # 1. Base query structure
    columns = [
        "event_id", "event_time", "timestamp_epoch", "source_topic", "measurement",
        "device_type", "hostname", "ip", "serial_number",
        "metric_name", "metric_value", "metric_unit", "severity",
        "site", "rack_name", "rack_position", "room_name", "manufacturer", "model",
        "asset_status", "environment", "business_unit",
        "enrichment_status", "enrichment_match_method", "enrichment_match_confidence",
        "last_modified_cmdb", "cached_at", "raw_fields", "raw_tags"
    ]
    
    values = [
        data.get("event_id"), parse_time(data.get("event_time")), data.get("timestamp"),
        data.get("source_topic"), data.get("measurement"), device_type, data.get("hostname"),
        data.get("ip"), data.get("serial_number"), data.get("metric_name"),
        data.get("metric_value"), data.get("metric_unit"), data.get("severity"),
        data.get("site"), data.get("rack_name"), data.get("rack_position"),
        data.get("room_name"), data.get("manufacturer"), data.get("model"),
        data.get("asset_status"), data.get("environment"), data.get("business_unit"),
        data.get("enrichment_status"), data.get("enrichment_match_method"),
        data.get("enrichment_match_confidence"), parse_time(data.get("last_modified_cmdb")),
        parse_time(data.get("cached_at")), json.dumps(data.get("raw_fields", {})),
        json.dumps(data.get("raw_tags", {}))
    ]

    # 2. Map raw_fields
    raw_fields = data.get("raw_fields", {})
    for rf_key, rf_val in raw_fields.items():
        if rf_key in RAW_FIELD_MAP and rf_val is not None:
            col_name, col_type = RAW_FIELD_MAP[rf_key]
            try:
                val = col_type(rf_val)
                if col_name not in columns:
                    columns.append(col_name)
                    values.append(val)
            except (ValueError, TypeError):
                pass
        # Unmapped keys will still be saved in JSONB 'raw_fields'

    # 3. Map raw_tags
    raw_tags = data.get("raw_tags", {})
    for rt_key, rt_val in raw_tags.items():
        if rt_key in RAW_TAGS_MAP and rt_val is not None:
            target_col = RAW_TAGS_MAP[rt_key].get(device_type)
            if target_col and target_col not in columns:
                columns.append(target_col)
                values.append(str(rt_val))

    # 4. Execute UPSERT
    placeholders = ",".join(["%s"] * len(columns))
    updates = ",".join([f"{col}=EXCLUDED.{col}" for col in columns if col != "event_id"])
    
    query = f"""
        INSERT INTO dcim_events ({",".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (event_id) DO UPDATE SET {updates};
    """
    
    cur.execute(query, values)

def main():
    logger.info("Starting DCIM Postgres Consumer (Full Schema V1)")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id='dcim_postgres_consumer_full_schema_v1',
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))
    )

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        count = 0
        for message in consumer:
            if not message.value or 'event_id' not in message.value:
                continue
            
            try:
                process_message(message.value, cur)
                count += 1
                if count % 100 == 0:
                    conn.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                conn.rollback()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.commit()
            cur.close()
            conn.close()

if __name__ == "__main__":
    main()
