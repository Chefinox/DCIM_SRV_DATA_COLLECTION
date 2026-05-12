#!/usr/bin/env python3
"""
DCIM PostgreSQL Consumer — Hybrid Schema (V2)
Dedicated columns untuk metric penting + JSONB untuk semua raw_fields.
"""
import json, logging, os, uuid
from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import Json

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     "192.168.101.73",
    "port":     5432,
    "dbname":   "dcim_sot",
    "user":     "sot_admin",
    "password": "Inovasi@0918"
}

# ── Mapping raw_fields → kolom dedicated ─────────────────────────────────────
# Hanya field yang punya kolom di tabel. Sisanya otomatis masuk JSONB.
COLUMN_MAP = {
    # UPS
    "upsBatteryCapacity":  ("ups_battery_capacity",     int),
    "upsBatteryRuntime":   ("ups_battery_runtime",      int),
    "upsBatteryTemp":      ("ups_battery_temp",         float),
    "upsBatteryStatus":    ("ups_battery_status",       int),
    "upsInputVoltage":     ("ups_input_voltage",        float),
    "upsOutputVoltage":    ("ups_output_voltage",       float),
    "upsOutputLoad":       ("ups_output_load",          int),
    "upsSecondsOnBattery": ("ups_seconds_on_battery",   int),

    # NAS
    "diskStatus":          ("nas_disk_status",          int),
    "diskTemp":            ("nas_disk_temp",            float),
    "system_temp":         ("nas_system_temp",          float),

    # Network Switch
    "if_name":             ("net_if_name",              str),
    "ifOperStatus":        ("net_if_oper_status",       int),
    "if_oper_status":      ("net_if_oper_status",       int),   # alias
    "ifAdminStatus":       ("net_if_admin_status",      int),
    "if_in_octets":        ("net_if_in_octets",         int),   # 64-bit
    "if_out_octets":       ("net_if_out_octets",        int),   # 64-bit
    "ifInErrors":          ("net_if_in_errors",         int),
    "ifOutErrors":         ("net_if_out_errors",        int),
    "ifSpeed":             ("net_if_speed",             int),

    # Server Redfish
    "reading_celsius":          ("srv_reading_celsius",          float),
    "reading_rpm":              ("srv_reading_rpm",              float),
    "lower_threshold_critical": ("srv_lower_threshold_critical", float),
    "lower_threshold_fatal":    ("srv_lower_threshold_fatal",    float),
    "upper_threshold_critical": ("srv_upper_threshold_critical", float),
    "upper_threshold_fatal":    ("srv_upper_threshold_fatal",    float),
    "power_watts":              ("srv_power_watts",              float),
    "power_input_watts":        ("srv_power_watts",              float),
    "power_output_watts":       ("srv_power_watts",              float),

    # CCTV
    "status_online":       ("cctv_status_online",       int),
    "status_text":         ("cctv_status_text",         str),
    "status":              ("cctv_status_text",         str),
}

# raw_tags yang perlu di-promote ke kolom dedicated per device_type
TAGS_TO_COLUMNS = {
    "name":   {"server": "srv_sensor_name", "server_redfish": "srv_sensor_name"},
    "health": {"server": "srv_health", "server_redfish": "srv_health"},
    "state":  {"server": "srv_state",  "server_redfish": "srv_state"},
}

# NAS: disk_id ada di raw_tags
NAS_DISK_ID_TAG = "diskID"

def parse_time(t_str):
    if not t_str: return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(t_str.replace('Z', '+00:00'))
    except:
        return None

def map_event(event: dict) -> dict:
    """Map enriched event ke row dictionary untuk INSERT."""
    dt = event.get("device_type", "unknown")
    rf = event.get("raw_fields", {})
    rt = event.get("raw_tags", {})

    # Shared fields — semua masuk kolom dedicated
    row = {
        "event_id":                   event.get("event_id") or str(uuid.uuid4()),
        "event_time":                 parse_time(event.get("event_time")),
        "timestamp_epoch":            event.get("timestamp"),
        "source_topic":               event.get("source_topic"),
        "measurement":                event.get("measurement"),
        "device_type":                dt,
        "hostname":                   event.get("hostname"),
        "ip":                         event.get("ip"),
        "serial_number":              event.get("serial_number"),
        "metric_name":                event.get("metric_name"),
        "metric_value":               event.get("metric_value"),
        "metric_unit":                event.get("metric_unit"),
        "severity":                   event.get("severity"),
        "site":                       event.get("site"),
        "rack_name":                  event.get("rack_name"),
        "rack_position":              event.get("rack_position"),
        "room_name":                  event.get("room_name"),
        "manufacturer":               event.get("manufacturer"),
        "model":                      event.get("model"),
        "asset_status":               event.get("asset_status"),
        "environment":                event.get("environment"),
        "business_unit":              event.get("business_unit"),
        "enrichment_status":          event.get("enrichment_status"),
        "enrichment_match_method":    event.get("enrichment_match_method"),
        "enrichment_match_confidence":event.get("enrichment_match_confidence"),
        "last_modified_cmdb":         parse_time(event.get("last_modified_cmdb")),
        "cached_at":                  parse_time(event.get("cached_at")),
        "raw_fields":                 Json(rf),
        "raw_tags":                   Json(rt),
    }

    # Map raw_fields ke kolom dedicated
    unmapped = []
    for rf_key, rf_val in rf.items():
        if rf_key in COLUMN_MAP:
            col, cast = COLUMN_MAP[rf_key]
            # Jangan overwrite jika sudah ada nilai (alias handling)
            if col not in row or row.get(col) is None:
                try:
                    row[col] = cast(rf_val) if rf_val is not None else None
                except (ValueError, TypeError):
                    row[col] = None
        else:
            unmapped.append(rf_key)

    # Promote raw_tags ke kolom dedicated
    for tag_key, device_map in TAGS_TO_COLUMNS.items():
        if dt in device_map and tag_key in rt:
            row[device_map[dt]] = rt[tag_key]

    # NAS disk_id dari raw_tags
    if dt == "nas" and NAS_DISK_ID_TAG in rt:
        row["nas_disk_id"] = rt[NAS_DISK_ID_TAG]

    return row

def upsert(cursor, row: dict):
    cols = list(row.keys())
    vals = list(row.values())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    update_set = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "event_id"
    )
    sql = f"""
        INSERT INTO dcim_events ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (event_id, event_time) DO UPDATE SET
        {update_set}, inserted_at = NOW()
    """
    cursor.execute(sql, vals)

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    consumer = KafkaConsumer(
        "dcim.enriched.events",
        bootstrap_servers=["localhost:9092"],
        group_id="dcim-postgres-consumer-v2",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=False,
        max_poll_records=100
    )

    log.info(json.dumps({"event": "consumer_started_v2", "topic": "dcim.enriched.events"}))
    batch_size = 50
    batch = []

    for msg in consumer:
        try:
            row = map_event(msg.value)
            batch.append(row)
            if len(batch) >= batch_size:
                for r in batch:
                    upsert(cur, r)
                conn.commit()
                consumer.commit()
                log.info(json.dumps({"event": "batch_committed", "count": len(batch)}))
                batch.clear()
        except Exception as e:
            conn.rollback()
            log.error(json.dumps({
                "event": "insert_error",
                "error": str(e),
                "event_id": msg.value.get("event_id","?")
            }))

if __name__ == "__main__":
    main()
