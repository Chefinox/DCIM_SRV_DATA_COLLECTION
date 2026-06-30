#!/usr/bin/env python3
"""
DCIM PostgreSQL Consumer — Hybrid Schema (V2) - Wrapped in V4 Structure
"""
import json, logging, os, uuid, time
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField
import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA
import psycopg2
from psycopg2.extras import Json

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# Konfigurasi Database (v3.4 Production)
import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.configs.database import get_db_config

DB_CONFIG = get_db_config()

ASSET_CACHE = {}
ASSET_CACHE_TS = 0
ASSET_CACHE_TTL = 300

def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("unknown", "null", "none", "no_identifier"):
        return None
    return text

def _plain_ip(value):
    text = _clean(value)
    if not text:
        return None
    return text.split("/")[0]

def _load_asset_cache():
    global ASSET_CACHE_TS
    now = time.time()
    if ASSET_CACHE and now - ASSET_CACHE_TS < ASSET_CACHE_TTL:
        return ASSET_CACHE
    cache = {}
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT serial_number, hostname, ip::text, device_type,
                   manufacturer, model, site, rack_name, asset_status,
                   ralph_id, ralph_endpoint
            FROM unified_assets
        """)
        for sn, hostname, ip, device_type, manufacturer, model, site, rack_name, asset_status, ralph_id, ralph_endpoint in cur.fetchall():
            meta = {
                "serial_number": sn,
                "hostname": hostname,
                "ip": _plain_ip(ip),
                "device_type": device_type,
                "manufacturer": manufacturer,
                "model": model,
                "site": site,
                "rack_name": rack_name,
                "asset_status": asset_status,
                "ralph_id": ralph_id,
                "ralph_endpoint": ralph_endpoint,
            }
            for key in (sn, hostname, _plain_ip(ip)):
                key = _clean(key)
                if key:
                    cache[key.lower()] = meta
        cur.close()
        conn.close()
        ASSET_CACHE.clear()
        ASSET_CACHE.update(cache)
        ASSET_CACHE_TS = now
    except Exception as exc:
        log.warning(f"asset cache refresh failed: {exc}")
    return ASSET_CACHE

def _asset_lookup(sn, ip, hostname):
    cache = _load_asset_cache()
    for key in (_clean(sn), _plain_ip(ip), _clean(hostname)):
        if key and key.lower() in cache:
            return cache[key.lower()]
    return None

# ── Mapping raw_fields → kolom dedicated ─────────────────────────────────────
COLUMN_MAP = {
    "battery_capacity":       ("ups_battery_capacity",     int),
    "battery_runtime_remain": ("ups_battery_runtime",      int),
    "battery_temp":           ("ups_battery_temp",         float),
    "status":                 ("ups_battery_status",       int),
    "input_voltage":          ("ups_input_voltage",        float),
    "output_voltage":         ("ups_output_voltage",       float),
    "output_load":            ("ups_output_load",          int),
    "diskStatus":          ("nas_disk_status",          int),
    "diskTemp":            ("nas_disk_temp",            float),
    "system_temp":         ("nas_system_temp",          float),
    "if_name":             ("net_if_name",              str),
    "ifOperStatus":        ("net_if_oper_status",       int),
    "if_oper_status":      ("net_if_oper_status",       int),
    "ifAdminStatus":       ("net_if_admin_status",      int),
    "if_in_octets":        ("net_if_in_octets",         int),
    "if_out_octets":       ("net_if_out_octets",        int),
    "ifInErrors":          ("net_if_in_errors",         int),
    "ifOutErrors":         ("net_if_out_errors",        int),
    "ifSpeed":             ("net_if_speed",             int),
    "reading_celsius":          ("srv_reading_celsius",          float),
    "reading_rpm":              ("srv_reading_rpm",              float),
    "lower_threshold_critical": ("srv_lower_threshold_critical", float),
    "lower_threshold_fatal":    ("srv_lower_threshold_fatal",    float),
    "upper_threshold_critical": ("srv_upper_threshold_critical", float),
    "upper_threshold_fatal":    ("srv_upper_threshold_fatal",    float),
    "power_watts":              ("srv_power_watts",              float),
    "power_input_watts":        ("srv_power_watts",              float),
    "power_output_watts":       ("srv_power_watts",              float),
    "firmware":                 ("srv_firmware",                 str),
    "bios_version":             ("srv_bios_version",             str),
    "BiosVersion":              ("srv_bios_version",             str),
    "system_name":              ("srv_system_name",              str),
    "cpu_count":                ("srv_cpu_count",                int),
    "memory_total_mb":          ("srv_memory_total_mb",          int),
    "status_online":       ("cctv_status_online",       int),
    "status_text":         ("cctv_status_text",         str),
    "status":              ("cctv_status_text",         str),
}

TAGS_TO_COLUMNS = {
    "name":   {"server": "srv_sensor_name", "server_redfish": "srv_sensor_name"},
    "health": {"server": "srv_health", "server_redfish": "srv_health"},
    "state":  {"server": "srv_state",  "server_redfish": "srv_state"},
}

NAS_DISK_ID_TAG = "diskID"

def parse_time(t_str):
    if not t_str: return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(t_str.replace('Z', '+00:00'))
    except:
        return None

def map_event(event: dict) -> dict:
    dt = event.get("device_type", "unknown")
    rf = event.get("raw_fields", {})
    rt = event.get("raw_tags", {})
    hostname = event.get("hostname")
    ip = event.get("ip") or rt.get("ip") or rt.get("agent_host") or rf.get("ip") or rf.get("ip_address")
    sn = event.get("serial_number")
    model = event.get("model") or rt.get("model") or rf.get("model")
    manufacturer = event.get("manufacturer") or rt.get("manufacturer") or rf.get("manufacturer")

    if dt in ("cctv", "nvr") and _clean(model) and str(model).upper().startswith("DS-"):
        manufacturer = manufacturer or "Hikvision"

    asset = _asset_lookup(sn, ip, hostname)
    if asset:
        if not _clean(sn) or str(sn).upper() in ("NO_SN", "NO_IDENTIFIER"):
            sn = asset.get("serial_number") or sn
        hostname = hostname if _clean(hostname) and str(hostname).lower() != "unknown" else asset.get("hostname")
        ip = ip or asset.get("ip")
        manufacturer = manufacturer or asset.get("manufacturer")
        model = model if _clean(model) else asset.get("model")

    if dt == "ups" and not _plain_ip(ip):
        ip = rt.get("agent_host") or rt.get("ip")

    row = {
        "event_id":                   event.get("event_id") or str(uuid.uuid4()),
        "event_time":                 parse_time(event.get("event_time")),
        "timestamp_epoch":            event.get("timestamp"),
        "source_topic":               event.get("source_topic"),
        "measurement":                event.get("measurement"),
        "device_type":                dt,
        "hostname":                   hostname,
        "ip":                         ip,
        "serial_number":              sn,
        "metric_name":                event.get("metric_name"),
        "metric_value":               event.get("metric_value"),
        "metric_unit":                event.get("metric_unit"),
        "severity":                   event.get("severity"),
        "site":                       event.get("site") or (asset or {}).get("site"),
        "rack_name":                  event.get("rack_name") or (asset or {}).get("rack_name"),
        "rack_position":              event.get("rack_position"),
        "room_name":                  event.get("room_name"),
        "manufacturer":               manufacturer,
        "model":                      model,
        "firmware":                   event.get("firmware"),
        "asset_status":               event.get("asset_status") or (asset or {}).get("asset_status"),
        "environment":                event.get("environment"),
        "business_unit":              event.get("business_unit"),
        "enrichment_status":          "FULL" if asset else event.get("enrichment_status"),
        "enrichment_match_method":    "local_asset_cache" if asset else event.get("enrichment_match_method"),
        "enrichment_match_confidence":"high" if asset else event.get("enrichment_match_confidence"),
        "last_modified_cmdb":         parse_time(event.get("last_modified_cmdb")),
        "cached_at":                  parse_time(event.get("cached_at")),
        "raw_fields":                 Json(rf),
        "raw_tags":                   Json(rt),
    }
    for rf_key, rf_val in rf.items():
        if rf_key in COLUMN_MAP:
            col, cast = COLUMN_MAP[rf_key]
            if col not in row or row.get(col) is None:
                try:
                    row[col] = cast(rf_val) if rf_val is not None else None
                except (ValueError, TypeError):
                    row[col] = None
    for tag_key, device_map in TAGS_TO_COLUMNS.items():
        if dt in device_map and tag_key in rt:
            row[device_map[dt]] = rt[tag_key]
    if dt == "nas" and NAS_DISK_ID_TAG in rt:
        row["nas_disk_id"] = rt[NAS_DISK_ID_TAG]

    if event.get("metric_name") == "inventory_snapshot" or event.get("measurement") == "server_inventory":
        if "processors" in rf: row["srv_cpu_components"] = Json(rf["processors"])
        if "memory" in rf: row["srv_memory_components"] = Json(rf["memory"])
        if "disks" in rf: row["srv_disk_components"] = Json(rf["disks"])
        if "nics" in rf: 
            rt_copy = dict(rt)
            rt_copy["nics"] = rf["nics"]
            row["raw_tags"] = Json(rt_copy)

    return row

def update_relational_tables(cursor, row: dict, rf: dict):
    ip = row.get("ip")
    if not ip: return
    
    # 1. Disks
    cursor.execute("DELETE FROM dcim_server_disks WHERE server_ip = %s", (ip,))
    for d in rf.get("disks", []):
        cursor.execute("""
            INSERT INTO dcim_server_disks (server_ip, serial_number, model_name, size_gb, firmware_version, slot)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (ip, d.get("serial_number"), d.get("model_name"), d.get("size"), d.get("firmware_version"), str(d.get("slot")) if d.get("slot") is not None else None))

    # 2. RAM
    cursor.execute("DELETE FROM dcim_server_ram WHERE server_ip = %s", (ip,))
    for m in rf.get("memory", []):
        cursor.execute("""
            INSERT INTO dcim_server_ram (server_ip, model_name, size_mb, speed_mhz)
            VALUES (%s, %s, %s, %s)
        """, (ip, m.get("model_name"), m.get("size"), m.get("speed")))

    # 3. Processors
    cursor.execute("DELETE FROM dcim_server_processors WHERE server_ip = %s", (ip,))
    for p in rf.get("processors", []):
        cursor.execute("""
            INSERT INTO dcim_server_processors (server_ip, model_name, cores, logical_cores, speed_mhz)
            VALUES (%s, %s, %s, %s, %s)
        """, (ip, p.get("model_name"), p.get("cores"), p.get("threads"), p.get("speed")))

    # 4. NICs
    cursor.execute("DELETE FROM dcim_server_nics WHERE server_ip = %s", (ip,))
    for n in rf.get("nics", []):
        raw_speed = n.get("raw_speed_mbps", 0)
        speed_gbps = int(raw_speed / 1000) if raw_speed else 0
        cursor.execute("""
            INSERT INTO dcim_server_nics (server_ip, label, mac_address, speed_gbps, model_name)
            VALUES (%s, %s, %s, %s, %s)
        """, (ip, n.get("label"), n.get("mac"), speed_gbps, n.get("model_name")))

def upsert(cursor, row: dict):
    cols = list(row.keys())
    vals = list(row.values())
    placeholders = ", ".join(["%s"] * len(cols))
    col_names = ", ".join(cols)
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "event_id")
    sql = f"""
        INSERT INTO dcim_events ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (event_id, event_time) DO UPDATE SET
        {update_set}, inserted_at = NOW()
    """
    cursor.execute(sql, vals)

def run():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()
    
    schema_registry_conf = {'url': 'http://localhost:8081'}
    schema_registry_client = SchemaRegistryClient(schema_registry_conf)
    avro_deserializer = AvroDeserializer(schema_registry_client, ENRICHED_EVENT_SCHEMA)
    
    consumer_conf = {
        'bootstrap.servers': 'localhost:9094',
        'group.id': 'dcim-postgres-consumer-v2',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': False,
        'security.protocol': 'SSL',
        'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
        'enable.ssl.certificate.verification': False
    }
    consumer = Consumer(consumer_conf)
    consumer.subscribe(["dcim.enriched.events"])
    
    log.info(json.dumps({"event": "consumer_started_v2_rollback", "topic": "dcim.enriched.events"}))
    batch_size = 50
    batch = []
    
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            log.error(f"Consumer error: {msg.error()}")
            continue
            
        try:
            ctx = SerializationContext("dcim.enriched.events", MessageField.VALUE)
            msg_val = avro_deserializer(msg.value(), ctx)
            if not msg_val: continue
            
            # Parse raw JSON strings back to dict for the legacy logic
            if isinstance(msg_val.get('raw_fields'), str):
                msg_val['raw_fields'] = json.loads(msg_val['raw_fields'])
            if isinstance(msg_val.get('raw_tags'), str):
                msg_val['raw_tags'] = json.loads(msg_val['raw_tags'])
                
            row = map_event(msg_val)
            if not row.get("event_time"):
                log.warning(f"Skipping event_id {row.get('event_id')} due to missing event_time")
                continue
            batch.append((row, msg_val.get("raw_fields", {})))
            if len(batch) >= batch_size:
                for r, rf in batch:
                    upsert(cur, r)
                    if r.get("metric_name") == "inventory_snapshot" or r.get("measurement") == "server_inventory":
                        update_relational_tables(cur, r, rf)
                conn.commit()
                consumer.commit(asynchronous=False)
                log.info(json.dumps({"event": "batch_committed", "count": len(batch)}))
                batch.clear()
        except Exception as e:
            conn.rollback()
            log.error(json.dumps({
                "event": "insert_error",
                "error": str(e),
                "event_id": msg_val.get("event_id","?") if 'msg_val' in locals() and msg_val else "?"
            }))

if __name__ == "__main__":
    run()
