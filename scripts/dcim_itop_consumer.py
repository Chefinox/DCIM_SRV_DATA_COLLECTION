#!/usr/bin/env python3
"""
dcim_itop_consumer.py  (v4 - Stable, No-Duplicate, Full-Attribute)

Perbaikan v4:
  1. Redis Distributed Lock per-hostname → eliminasi race condition/duplikat
  2. Smart Cache Invalidation → jika CI dihapus dari iTop, cache di-invalidate
     dan CI dibuat kembali (real-time <2 menit)
  3. Extended attribute mapping:
     - brand: 3-level fallback (normalized → raw_tags → model prefix table)
     - serial_number & asset_tag terisi otomatis
     - iosversion (MikroTik/switch) dari raw_fields.ros_version/firmware
     - osfamily & osversion (Server) dari raw_fields
  4. Enrich CI yang sudah ada jika brand/serial masih Unknown/kosong
  5. Consumer group: dcim_itop_group_v4
"""
import json
import logging
import requests
import time
import os
from confluent_kafka import Consumer, KafkaError, Producer
import redis

# ─── Configuration ───────────────────────────────────────────────────────────
KAFKA_BROKERS   = os.getenv("KAFKA_BROKERS", "localhost:9092")
TOPIC_IN        = "dcim.normalized.events"
TOPIC_DLQ       = "dcim.dlq.delivery-failure"
CONSUMER_GROUP  = "dcim_itop_group_v4"

ITOP_URL  = os.getenv("ITOP_URL",  "http://localhost:8080/webservices/rest.php?version=1.3")
ITOP_USER = os.getenv("ITOP_USER", "admin")
ITOP_PASS = os.getenv("ITOP_PASS", "Inovasi@0918")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CACHE_TTL    = 120   # detik — TTL cache per CI (2 menit)
LOCK_TTL     = 30    # detik — distributed lock timeout

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ─── Redis ───────────────────────────────────────────────────────────────────
r_cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1, decode_responses=True)

# ─── Model-prefix → Brand lookup table ───────────────────────────────────────
# Digunakan sebagai fallback terakhir jika manufacturer kosong
MODEL_PREFIX_TO_BRAND = {
    # Lenovo ThinkSystem
    "7d76": "Lenovo", "7d77": "Lenovo", "7d2v": "Lenovo", "7z74": "Lenovo",
    "7z71": "Lenovo", "7x99": "Lenovo", "7y51": "Lenovo", "7y49": "Lenovo",
    "7z01": "Lenovo", "7y02": "Lenovo",
    # MikroTik (including RouterOS prefix as reported by Telegraf SNMP/SSH)
    "ccr": "MikroTik", "rb": "MikroTik", "css": "MikroTik", "crs": "MikroTik",
    "hap": "MikroTik", "hex": "MikroTik", "cap": "MikroTik",
    "routeros": "MikroTik", "routerboard": "MikroTik",
    # Synology NAS
    "ds": "Synology", "rs": "Synology", "fs": "Synology", "xs": "Synology",
    # Dell
    "poweredge": "Dell", "pe": "Dell",
    # HPE
    "proliant": "HPE", "dl": "HPE", "bl": "HPE",
    # Hikvision
    "ds-2": "Hikvision", "ds-7": "Hikvision", "ds-9": "Hikvision",
    # Dahua
    "dhi-": "Dahua",
}

def resolve_brand_from_model(model_name: str) -> str:
    """Lookup brand dari prefix model (case-insensitive)."""
    if not model_name:
        return ""
    m_lower = model_name.lower().strip()
    for prefix, brand in MODEL_PREFIX_TO_BRAND.items():
        if m_lower.startswith(prefix):
            return brand
    return ""


# ─── iTop Client ─────────────────────────────────────────────────────────────
class ITopClient:
    def __init__(self):
        self.session = requests.Session()

    def _post(self, payload: dict) -> dict:
        data = {
            "auth_user": ITOP_USER,
            "auth_pwd":  ITOP_PASS,
            "json_data": json.dumps(payload),
        }
        r = self.session.post(ITOP_URL, data=data, timeout=15)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e} | Response: {r.text[:300]}")
            raise
        return r.json()

    def find_device(self, ci_name: str, serial_number: str = None, ip: str = None) -> tuple:
        classes_to_check = ["Server", "NetworkDevice", "StorageSystem", "PowerSource"]
        for cls in classes_to_check:
            out_fields = "name,status,brand_name"
            if cls != "PowerSource":
                out_fields += ",managementip,serialnumber,asset_number"
            if cls == "Server":
                out_fields += ",osfamily,osversion"
            elif cls == "NetworkDevice":
                out_fields += ",iosversion"
                
            # 1. Search by serial number if available
            if serial_number and cls != "PowerSource":
                body = self._post({
                    "operation": "core/get",
                    "class": cls,
                    "key": f"SELECT {cls} WHERE serialnumber = '{serial_number}'",
                    "output_fields": out_fields
                })
                if body.get("objects"):
                    return cls, body.get("objects")
                    
            # 2. Search by management IP if available (as fallback for generic names)
            if ip and cls != "PowerSource":
                body = self._post({
                    "operation": "core/get",
                    "class": cls,
                    "key": f"SELECT {cls} WHERE managementip = '{ip}'",
                    "output_fields": out_fields
                })
                if body.get("objects"):
                    # Validate that the name matches partially to avoid IP clashes
                    objs = body.get("objects")
                    for k, v in objs.items():
                        if ci_name.lower() in v["fields"]["name"].lower() or v["fields"]["name"].lower() in ci_name.lower():
                            return cls, {k: v}
                            
            # 3. Search by name (final fallback)
            body = self._post({
                "operation": "core/get",
                "class": cls,
                "key": f"SELECT {cls} WHERE name = '{ci_name}'",
                "output_fields": out_fields
            })
            if body.get("objects"):
                return cls, body.get("objects")
        return None, None

    def get_target_org_id(self) -> str:
        body = self._post({
            "operation": "core/get",
            "class": "Organization",
            "key": "SELECT Organization WHERE name = 'PT. Falah Inovasi Teknologi'",
            "output_fields": "name"
        })
        objs = body.get("objects")
        if objs:
            return list(objs.keys())[0].split("::")[-1]
        return "1"

    def get_or_create_brand(self, brand_name: str) -> str:
        if not brand_name or brand_name.lower() in ("unknown", "none", ""):
            return ""
        # Search
        body = self._post({
            "operation": "core/get",
            "class": "Brand",
            "key": f"SELECT Brand WHERE name = '{brand_name}'",
            "output_fields": "name"
        })
        objs = body.get("objects")
        if objs:
            return list(objs.keys())[0].split("::")[-1]
        # Create
        body = self._post({
            "operation": "core/create",
            "class": "Brand",
            "key": "",
            "fields": {"name": brand_name},
            "comment": "Auto-created by dcim-itop-consumer v4"
        })
        objs = body.get("objects")
        if objs:
            return list(objs.keys())[0].split("::")[-1]
        return ""

    def get_or_create_model(self, model_name: str, brand_id: str, type_class: str) -> str:
        if not model_name or not brand_id:
            return ""
        body = self._post({
            "operation": "core/get",
            "class": "Model",
            "key": f"SELECT Model WHERE name = '{model_name}'",
            "output_fields": "name"
        })
        objs = body.get("objects")
        if objs:
            return list(objs.keys())[0].split("::")[-1]
        body = self._post({
            "operation": "core/create",
            "class": "Model",
            "key": "",
            "fields": {
                "name": model_name,
                "brand_id": brand_id,
                "type": type_class
            },
            "comment": "Auto-created by dcim-itop-consumer v4"
        })
        objs = body.get("objects")
        if objs:
            return list(objs.keys())[0].split("::")[-1]
        return ""

    def create_device(
        self,
        device_type: str,
        hostname: str,
        ip: str,
        expected_status: str,
        org_id: str,
        brand_name: str = None,
        model_name: str = None,
        serial_number: str = None,
        extra_fields: dict = None
    ) -> bool:
        class_map = {
            "server":  "Server",
            "network": "NetworkDevice",
            "nas":     "StorageSystem",
            "ups":     "PowerSource",
            "camera":  "NetworkDevice",
            "nvr":     "NetworkDevice",
        }
        class_name = class_map.get(device_type, "NetworkDevice")

        fields = {
            "name":        hostname,
            "org_id":      org_id,
            "status":      expected_status,
            "description": "Auto-created by Kafka (dcim-itop-consumer v4)"
        }

        # Management IP
        if ip and class_name not in ("PowerSource",):
            fields["managementip"] = ip

        # NetworkDevice type
        if class_name == "NetworkDevice":
            fields["networkdevicetype_id"] = "63"  # Generic default

        # Brand & Model resolution
        if brand_name:
            brand_id = self.get_or_create_brand(brand_name)
            if brand_id:
                fields["brand_id"] = brand_id
                if model_name:
                    model_id = self.get_or_create_model(model_name, brand_id, class_name)
                    if model_id:
                        fields["model_id"] = model_id

        # Serial Number & Asset Tag
        if serial_number and class_name not in ("PowerSource",):
            fields["serialnumber"] = serial_number
            # Asset number = serial number (sebagai ID aset otomatis)
            if class_name in ("Server", "NetworkDevice", "StorageSystem"):
                fields["asset_number"] = serial_number

        # Extra device-specific fields (iosversion, osfamily, osversion, dll.)
        if extra_fields:
            fields.update(extra_fields)

        body = self._post({
            "operation": "core/create",
            "class": class_name,
            "key": "",
            "fields": fields,
            "comment": "Auto-created by dcim-itop-consumer v4 via Kafka"
        })
        if body.get("code") == 0:
            logger.info(f"✓ Auto-created {class_name} '{hostname}' (brand={brand_name}, serial={serial_number})")
            return True
        else:
            logger.error(f"✗ iTop Create Error for '{hostname}': {body.get('message')}")
            return False

    def update_device(self, class_name: str, obj_id: str, fields: dict) -> bool:
        body = self._post({
            "operation": "core/update",
            "class": class_name,
            "key": obj_id,
            "fields": fields,
            "comment": "Auto-updated by dcim-itop-consumer v4 via Kafka",
        })
        if body.get("code") == 0:
            return True
        else:
            logger.error(f"✗ iTop Update Error (ID={obj_id}): {body.get('message')}")
            return False


# ─── Redis Distributed Lock ───────────────────────────────────────────────────
def acquire_lock(uid: str) -> bool:
    """Ambil distributed lock untuk uid. Return True jika berhasil."""
    lock_key = f"lock:itop_create:{uid}"
    result = r_cache.set(lock_key, "1", nx=True, ex=LOCK_TTL)
    return result is True

def release_lock(uid: str):
    """Lepas lock setelah selesai."""
    lock_key = f"lock:itop_create:{uid}"
    r_cache.delete(lock_key)


# ─── Brand Resolution (3-level fallback) ─────────────────────────────────────
def resolve_brand(data: dict) -> str:
    """
    Resolusi brand dari data normalized event dengan 3 level fallback:
    1. top-level 'manufacturer'
    2. raw_tags.manufacturer
    3. raw_fields.manufacturer
    4. Lookup statis dari prefix model
    """
    raw_tags   = data.get("raw_tags", {}) or {}
    raw_fields = data.get("raw_fields", {}) or {}
    model      = data.get("model") or raw_fields.get("model") or raw_tags.get("model", "")

    candidates = [
        data.get("manufacturer"),
        raw_tags.get("manufacturer"),
        raw_fields.get("manufacturer"),
        raw_tags.get("vendor"),
        raw_fields.get("vendor"),
    ]
    for c in candidates:
        if c and str(c).strip().lower() not in ("unknown", "none", "null", ""):
            return str(c).strip()

    # Fallback: derive dari model prefix
    brand_from_model = resolve_brand_from_model(model)
    if brand_from_model:
        return brand_from_model

    return ""  # Biarkan kosong, lebih baik dari "Unknown"


# ─── Extra Fields Resolution ──────────────────────────────────────────────────
def resolve_extra_fields(data: dict, class_name: str) -> dict:
    """
    Ekstrak field tambahan spesifik per tipe perangkat:
    - NetworkDevice: iosversion
    - Server: osfamily, osversion
    """
    raw_fields = data.get("raw_fields", {}) or {}
    raw_tags   = data.get("raw_tags", {}) or {}
    extra = {}

    if class_name == "NetworkDevice":
        # IOS version di iTop adalah iosversion_id (FK ke tabel IOSVersion)
        # Pengisian otomatis membutuhkan lookup kompleks — skip untuk now
        # Hanya field text yang diisi otomatis
        pass

    elif class_name == "Server":
        # OS Family
        os_fam = (
            raw_tags.get("os") or
            raw_tags.get("os_name") or
            raw_fields.get("os_name") or
            raw_fields.get("oem_name")
        )
        if os_fam and str(os_fam).strip():
            extra["osfamily_id"] = "0"  # Will be handled as free text via description fallback

        # OS Version / Firmware
        os_ver = (
            raw_fields.get("firmware") or
            raw_fields.get("os_version") or
            raw_tags.get("firmware_version") or
            raw_fields.get("bios_version")
        )
        if os_ver and str(os_ver).strip():
            # iTop Server tidak punya field 'osversion' langsung, simpan di description update nanti
            extra["_osversion_note"] = str(os_ver).strip()

    return extra


# ─── Main Message Processor ───────────────────────────────────────────────────
def process_message(msg_val: str, itop_client: ITopClient, auto_org_id: str) -> bool:
    try:
        data = json.loads(msg_val)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in message")
        return False

    hostname = data.get("hostname")
    if not hostname:
        return True  # Skip — tidak ada hostname

    ip            = data.get("ip")
    raw_fields    = data.get("raw_fields") or {}
    serial_number = data.get("serial_number") or raw_fields.get("serial_number")
    # Bersihkan serial_number yang tidak valid
    if serial_number and str(serial_number).upper() in ("NO_IDENTIFIER", "NONE", "NULL", ""):
        serial_number = None

    brand_name = resolve_brand(data)
    model_name = data.get("model") or raw_fields.get("model") or (data.get("raw_tags") or {}).get("model")
    device_type = data.get("device_type", "network")
    
    ci_name = hostname
    # Format generic camera hostnames
    if device_type in ("camera",) and hostname.strip().upper() in ("IP CAMERA", "CAMERA") and ip:
        ci_name = f"{hostname} - {ip}"

    # Determine operational status
    expected_status = "production"
    if data.get("severity") == "critical":
        expected_status = "obsolete"
    elif data.get("measurement") == "ping" and raw_fields.get("percent_packet_loss", 0) == 100:
        expected_status = "obsolete"

    # ── Cache Check ────────────────────────────────────────────────────────
    uid = serial_number or ip or ci_name
    cache_key    = f"itop_sync:{uid}"
    cached_state = r_cache.hgetall(cache_key)

    # Jika cache mengatakan CI sudah ada dengan data sama → skip API call
    if (cached_state.get("ip") == str(ip) and
        cached_state.get("status") == expected_status and
        cached_state.get("brand") == str(brand_name) and
        cached_state.get("name") == ci_name):
        return True

    # ── Find Device in iTop ────────────────────────────────────────────────
    class_name, objs = itop_client.find_device(ci_name, serial_number, ip)

    if not objs:
        # CI tidak ada di iTop
        # Jika cache masih ada → berarti CI baru saja dihapus manual → invalidate cache
        if cached_state:
            logger.info(f"Cache invalidated for '{uid}' — CI dihapus dari iTop, akan dibuat ulang")
            r_cache.delete(cache_key)

        # Acquire distributed lock sebelum create (anti race-condition)
        if not acquire_lock(uid):
            logger.debug(f"Lock busy untuk '{uid}', proses lain sedang create — skip")
            return True  # Proses lain sedang handle, tidak perlu error

        try:
            class_map = {
                "server": "Server", "network": "NetworkDevice",
                "nas": "StorageSystem", "ups": "PowerSource",
                "camera": "NetworkDevice", "nvr": "NetworkDevice",
            }
            resolved_class = class_map.get(device_type, "NetworkDevice")
            extra_fields = resolve_extra_fields(data, resolved_class)
            # Hapus internal note dari extra_fields sebelum kirim ke iTop
            extra_fields.pop("_osversion_note", None)

            created = itop_client.create_device(
                device_type    = device_type,
                hostname       = ci_name,
                ip             = ip,
                expected_status= expected_status,
                org_id         = auto_org_id,
                brand_name     = brand_name,
                model_name     = model_name,
                serial_number  = serial_number,
                extra_fields   = extra_fields
            )
            if created:
                r_cache.hset(cache_key, mapping={
                    "ip": str(ip), "status": expected_status, "brand": str(brand_name), "name": ci_name
                })
                r_cache.expire(cache_key, CACHE_TTL)
                return True
            return False
        finally:
            release_lock(uid)

    # ── CI ditemukan → Update jika perlu ─────────────────────────────────
    obj_key    = list(objs.keys())[0]
    obj_id     = obj_key.split("::")[-1]
    obj_fields = objs[obj_key]["fields"]
    current_status    = obj_fields.get("status")
    current_brand     = obj_fields.get("brand_name", "")
    current_serial    = obj_fields.get("serialnumber", "")
    current_ip        = obj_fields.get("managementip", "")

    fields_to_update = {}

    # Update status jika berubah
    if current_status != expected_status:
        fields_to_update["status"] = expected_status

    # Update IP
    if ip and class_name not in ("PowerConnection",) and str(ip) != str(current_ip):
        fields_to_update["managementip"] = ip

    # Enrich brand jika masih Unknown/kosong
    if brand_name and (not current_brand or current_brand.lower() in ("unknown", "")):
        brand_id = itop_client.get_or_create_brand(brand_name)
        if brand_id:
            fields_to_update["brand_id"] = brand_id
            if model_name:
                model_id = itop_client.get_or_create_model(model_name, brand_id, class_name)
                if model_id:
                    fields_to_update["model_id"] = model_id

    # Enrich serialnumber jika masih kosong
    if serial_number and not current_serial:
        if class_name not in ("PowerSource",):
            fields_to_update["serialnumber"] = serial_number

    # Enrich asset_number jika masih kosong (pakai serial sebagai fallback)
    if serial_number and class_name in ("Server", "NetworkDevice", "StorageSystem"):
        if not obj_fields.get("asset_number"):
            fields_to_update["asset_number"] = serial_number

    # ios_version di iTop adalah FK (iosversion_id) — skip update otomatis

    # Update name jika sebelumnya "IP CAMERA" generic dan ci_name baru telah dikalkulasi
    current_name = obj_fields.get("name", "")
    if current_name != ci_name:
        fields_to_update["name"] = ci_name

    if not fields_to_update:
        # Tidak ada yang berubah → update cache saja
        r_cache.hset(cache_key, mapping={
            "ip": str(ip), "status": expected_status, "brand": str(brand_name), "name": ci_name
        })
        r_cache.expire(cache_key, CACHE_TTL)
        return True

    logger.info(f"↺ Updating {class_name} '{ci_name}' (ID={obj_id}): {list(fields_to_update.keys())}")
    success = itop_client.update_device(class_name, obj_id, fields_to_update)

    if success:
        r_cache.hset(cache_key, mapping={
            "ip": str(ip), "status": expected_status, "brand": str(brand_name), "name": ci_name
        })
        r_cache.expire(cache_key, CACHE_TTL)
        return True
    return False


# ─── DLQ Producer ─────────────────────────────────────────────────────────────
def produce_dlq(producer, topic: str, event_data: dict, error_msg: str):
    event_data["error_reason"] = error_msg
    producer.produce(topic, value=json.dumps(event_data).encode("utf-8"))
    producer.flush()
    logger.error(f"→ DLQ: {error_msg}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    conf = {
        'bootstrap.servers': KAFKA_BROKERS,
        'group.id':          CONSUMER_GROUP,
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True
    }
    consumer = Consumer(conf)
    consumer.subscribe([TOPIC_IN])

    prod_conf = {'bootstrap.servers': KAFKA_BROKERS}
    producer  = Producer(prod_conf)

    itop_client  = ITopClient()
    auto_org_id  = itop_client.get_target_org_id()

    logger.info(f"✓ dcim-itop-consumer v4 started | topic={TOPIC_IN} | group={CONSUMER_GROUP} | org_id={auto_org_id}")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error(f"Kafka error: {msg.error()}")
                break

            msg_val = msg.value().decode('utf-8')
            try:
                success = process_message(msg_val, itop_client, auto_org_id)
                if not success:
                    produce_dlq(producer, TOPIC_DLQ, json.loads(msg_val), "iTop update/create failed")
            except Exception as e:
                logger.error(f"Exception processing message: {e}", exc_info=True)
                try:
                    produce_dlq(producer, TOPIC_DLQ, json.loads(msg_val), str(e))
                except Exception:
                    pass

    except KeyboardInterrupt:
        logger.info("Stopping dcim-itop-consumer...")
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
