#!/usr/bin/env python3
"""
dcim_itop_consumer.py  (v8 - Stable, No-Duplicate, Full-Attribute)

Version history:
  v4: Redis Distributed Lock, Smart Cache, Extended attributes
  v8: NAS NIC sync, PowerSource fix, HW fetch for network/nvr/ups,
      statement_timeout 10s, nb_u field, storage_id fix

Perbaikan v8:
  1. Redis Distributed Lock per-hostname → eliminasi race condition/duplikat
  2. Smart Cache Invalidation → jika CI dihapus dari iTop, cache di-invalidate
     dan CI dibuat kembali (real-time <2 menit)
  3. Extended attribute mapping:
     - brand: 3-level fallback (normalized → raw_tags → model prefix table)
     - serial_number & asset_tag terisi otomatis
     - iosversion (MikroTik/switch) dari raw_fields.ros_version/firmware
     - osfamily & osversion (Server) dari raw_fields
  4. Enrich CI yang sudah ada jika brand/serial masih Unknown/kosong
  5. Consumer group: dcim_itop_group_v8
"""
import json
import logging
import requests
import time
import requests
import time
import os
from confluent_kafka import Consumer, KafkaError, Producer
import redis

# Custom utils for Postgres / Ralph hardware fallback
from itop_sync_utils import get_server_hardware, get_network_hardware

# ─── Configuration ───────────────────────────────────────────────────────────
KAFKA_BROKERS   = os.getenv("KAFKA_BROKERS", "localhost:9092")
TOPIC_IN        = "dcim.normalized.events"
TOPIC_DLQ       = "dcim.dlq.delivery-failure"
CONSUMER_GROUP  = "dcim_itop_group_v8"

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
        self.url = ITOP_URL
        self.auth_user = ITOP_USER
        self.auth_pwd = ITOP_PASS
        # Dictionary untuk memory cache lookup sederhana (mempercepat proses)
        self._mem_cache = {}
        self.session = requests.Session()

    def _post(self, payload: dict) -> dict:
        data = {
            "auth_user": self.auth_user,
            "auth_pwd":  self.auth_pwd,
            "json_data": json.dumps(payload),
        }
        r = self.session.post(self.url, data=data, timeout=15)
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {e} | Response: {r.text[:300]}")
            raise
        return r.json()

    # ── Device type → iTop class mapping (shared by resolve_class & create_device) ──
    _CLASS_MAP = {
        "server":      "Server",
        "network":     "NetworkDevice",
        "network_switch": "NetworkDevice",
        "nas":         "NAS",
        "ups":         "PowerSource",
        "camera":      "Peripheral",
        "cctv":        "Peripheral",
        "nvr":         "NetworkDevice",
    }

    def resolve_class(self, device_type: str) -> str:
        """Map device_type string to iTop CI class name."""
        return self._CLASS_MAP.get(str(device_type).lower().strip(), "NetworkDevice")

    def find_device(self, ci_name: str, serial_number: str = None, ip: str = None) -> tuple:
        classes_to_check = ["Server", "NetworkDevice", "NAS", "StorageSystem", "PowerSource", "Peripheral"]
        for cls in classes_to_check:
            out_fields = "name,status,brand_name"
            if cls not in ("PowerSource", "Peripheral"):
                out_fields += ",managementip"
            if cls != "PowerSource":
                out_fields += ",serialnumber,asset_number"
            if cls == "Server":
                out_fields += ",osfamily_id,osversion_id,cpu,ram,location_id,rack_id,nb_u"
            elif cls == "NetworkDevice":
                out_fields += ",iosversion_id,nb_u,ram,location_id,rack_id,networkdevicetype_id"
            elif cls == "NAS":
                out_fields += ",location_id,rack_id"
                
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
            if ip and cls not in ("PowerSource", "Peripheral"):
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
                
            # 4. If not found, try the other hostname prefix variant (SRV- vs SERVER-)
            if cls == "Server":
                alt_name = ci_name.replace('SRV-', 'SERVER-') if ci_name.startswith('SRV-') else ci_name.replace('SERVER-', 'SRV-')
                body = self._post({
                    "operation": "core/get",
                    "class": cls,
                    "key": f"SELECT {cls} WHERE name = '{alt_name}'",
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
        cache_key = f"brand:{brand_name}"
        if cache_key in self._mem_cache: return self._mem_cache[cache_key]
        
        # Search
        body = self._post({
            "operation": "core/get",
            "class": "Brand",
            "key": f"SELECT Brand WHERE name = '{brand_name}'",
            "output_fields": "name"
        })
        objs = body.get("objects")
        if objs:
            res = list(objs.keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        # Create
        body = self._post({
            "operation": "core/create",
            "class": "Brand",
            "key": "",
            "fields": {"name": brand_name},
            "comment": "Auto-created by dcim-itop-consumer v8"
        })
        objs = body.get("objects")
        if objs:
            res = list(objs.keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        return ""

    def get_or_create_model(self, model_name: str, brand_id: str, type_class: str) -> str:
        if not model_name or not brand_id:
            return ""
        cache_key = f"model:{model_name}:{brand_id}"
        if cache_key in self._mem_cache: return self._mem_cache[cache_key]
        
        body = self._post({
            "operation": "core/get",
            "class": "Model",
            "key": f"SELECT Model WHERE name = '{model_name}'",
            "output_fields": "name"
        })
        objs = body.get("objects")
        if objs:
            res = list(objs.keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        body = self._post({
            "operation": "core/create",
            "class": "Model",
            "key": "",
            "fields": {
                "name": model_name,
                "brand_id": brand_id,
                "type": type_class
            },
            "comment": "Auto-created by dcim-itop-consumer v8"
        })
        objs = body.get("objects")
        if objs:
            res = list(objs.keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        return ""

    def get_or_create_location(self, loc_name: str, org_id: str) -> str:
        if not loc_name: return "0"
        cache_key = f"location:{loc_name}"
        if cache_key in self._mem_cache: return self._mem_cache[cache_key]
        
        body = self._post({
            "operation": "core/get", "class": "Location",
            "key": f"SELECT Location WHERE name='{loc_name}'", "output_fields": "name"
        })
        if body.get("objects"):
            res = list(body["objects"].keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        
        body = self._post({
            "operation": "core/create", "class": "Location", "key": "",
            "fields": {"name": loc_name, "org_id": org_id},
            "comment": "Auto-created by dcim-itop-consumer v8"
        })
        if body.get("objects"):
            res = list(body["objects"].keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        return "0"

    def get_or_create_networkdevicetype(self, type_name: str) -> str:
        if not type_name: return "0"
        cache_key = f"networkdevicetype:{type_name}"
        if cache_key in self._mem_cache: return self._mem_cache[cache_key]
        
        body = self._post({
            "operation": "core/get", "class": "NetworkDeviceType",
            "key": f"SELECT NetworkDeviceType WHERE name='{type_name}'", "output_fields": "name"
        })
        if body.get("objects"):
            res = list(body["objects"].keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        
        body = self._post({
            "operation": "core/create", "class": "NetworkDeviceType", "key": "",
            "fields": {"name": type_name},
            "comment": "Auto-created by dcim-itop-consumer v8"
        })
        if body.get("objects"):
            res = list(body["objects"].keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        return "0"

    def get_or_create_iosversion(self, version_name: str) -> str:
        if not version_name: return "0"
        cache_key = f"iosversion:{version_name}"
        if cache_key in self._mem_cache: return self._mem_cache[cache_key]
        
        body = self._post({
            "operation": "core/get", "class": "IOSVersion",
            "key": f"SELECT IOSVersion WHERE name='{version_name}'", "output_fields": "name"
        })
        if body.get("objects"):
            res = list(body["objects"].keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        
        body = self._post({
            "operation": "core/create", "class": "IOSVersion", "key": "",
            "fields": {"name": version_name},
            "comment": "Auto-created by dcim-itop-consumer v8"
        })
        if body.get("objects"):
            res = list(body["objects"].keys())[0].split("::")[-1]
            self._mem_cache[cache_key] = res
            return res
        return "0"

    def get_or_create_rack(self, rack_name: str, loc_id: str, org_id: str) -> str:
        if not rack_name or loc_id == "0": return "0"
        
        body = self._post({
            "operation": "core/get", "class": "Rack",
            "key": f"SELECT Rack WHERE name='{rack_name}' AND org_id='{org_id}'", "output_fields": "location_id"
        })
        
        if body.get("objects"):
            rack_id = list(body["objects"].keys())[0].split("::")[-1]
            existing_loc_id = body["objects"][f"Rack::{rack_id}"]["fields"].get("location_id")
            
            if str(existing_loc_id) != str(loc_id):
                self._post({
                    "operation": "core/update", "class": "Rack", "key": rack_id,
                    "fields": {"location_id": loc_id},
                    "comment": "Auto-updated location by dcim-itop-consumer v8"
                })
            return rack_id
        
        body = self._post({
            "operation": "core/create", "class": "Rack", "key": "",
            "fields": {"name": rack_name, "org_id": org_id, "location_id": loc_id},
            "comment": "Auto-created by dcim-itop-consumer v8"
        })
        if body.get("objects"): return list(body["objects"].keys())[0].split("::")[-1]
        return "0"

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
    ) -> str:
        class_name = self.resolve_class(device_type)

        fields = {
            "name":        hostname,
            "org_id":      org_id,
            "status":      expected_status,
            "description": "Auto-created by Kafka (dcim-itop-consumer v8)"
        }
        # Management IP
        if ip and class_name not in ("PowerSource", "Peripheral"):
            fields["managementip"] = ip

        # Brand & Model resolution (jika tersedia dari Kafka)
        if brand_name:
            brand_id = self.get_or_create_brand(brand_name)
            if brand_id:
                fields["brand_id"] = brand_id
                if model_name:
                    model_id = self.get_or_create_model(model_name, brand_id, class_name)
                    if model_id:
                        fields["model_id"] = model_id

        # Serial Number & Asset Tag
        if serial_number:
            fields["serialnumber"] = serial_number
            # Asset number = serial number (sebagai ID aset otomatis)
            if class_name in ("Server", "NetworkDevice", "StorageSystem", "NAS", "PowerSource"):
                fields["asset_number"] = serial_number

        # Extra device-specific fields (iosversion, osfamily, osversion, dll.)
        if extra_fields:
            fields.update(extra_fields)

        body = self._post({
            "operation": "core/create",
            "class": class_name,
            "key": "",
            "fields": fields,
            "comment": "Auto-created by dcim-itop-consumer v8 via Kafka"
        })
        if body.get("code") == 0:
            logger.info(f"✓ Auto-created {class_name} '{hostname}' (brand={brand_name}, serial={serial_number})")
            objs = body.get("objects", {})
            if objs:
                key = list(objs.keys())[0]
                return key.split("::")[1] if "::" in key else key
            return "created"
        else:
            logger.error(f"✗ iTop Create Error for '{hostname}': {body.get('message')}")
            return "" 

    def update_device(self, class_name: str, obj_id: str, fields: dict) -> str:
        body = self._post({
            "operation": "core/update",
            "class": class_name,
            "key": obj_id,
            "fields": fields,
            "comment": "Auto-updated by dcim-itop-consumer v8 via Kafka",
        })
        if body.get("code") == 0:
            return True
        else:
            logger.error(f"✗ iTop Update Error (ID={obj_id}): {body.get('message')}")
            return False

    def get_network_interfaces(self, server_id):
        body = self._post({
            "operation": "core/get",
            "class": "PhysicalInterface",
            "key": f"SELECT PhysicalInterface WHERE connectableci_id = '{server_id}'",
            "output_fields": "macaddress,name,speed,ipaddress"
        })
        return body.get("objects") or {}

    def create_network_interface(self, server_id, name, mac, speed_mbps, ip="", mask="", gateway=""):
        return self._post({
            "operation": "core/create",
            "class": "PhysicalInterface",
            "comment": "Auto-created interface",
            "fields": {
                "connectableci_id": server_id,
                "name": name,
                "macaddress": mac,
                "speed": str(speed_mbps),
                "ipaddress": ip,
                "ipmask": mask,
                "ipgateway": gateway
            }
        })

    def update_network_interface(self, interface_id, name, speed_mbps, ip="", mask="", gateway="", mac=""):
        fields = {
            "name": name,
            "speed": str(speed_mbps),
            "ipaddress": ip,
            "ipmask": mask,
            "ipgateway": gateway
        }
        if mac:
            fields["macaddress"] = mac
            
        return self._post({
            "operation": "core/update",
            "class": "PhysicalInterface",
            "comment": "Auto-updated interface",
            "key": interface_id,
            "fields": fields
        })

    def get_or_create_local_storage_system(self, hostname, org_id, location_id="0"):
        name = f"Local Storage - {hostname}"
        
        # Try exact name first, then alternate (SRV- vs SERVER-)
        names_to_try = [name]
        if hostname.startswith("SERVER-"):
            names_to_try.append(f"Local Storage - SRV-{hostname[7:]}")
        elif hostname.startswith("SRV-"):
            names_to_try.append(f"Local Storage - SERVER-{hostname[4:]}")
        
        for try_name in names_to_try:
            body = self._post({
                "operation": "core/get",
                "class": "StorageSystem",
                "key": f"SELECT StorageSystem WHERE name = '{try_name}'",
                "output_fields": "id,location_id"
            })
            objs = body.get("objects", {})
            if objs:
                key = list(objs.keys())[0]
                obj_id = key.split("::")[1] if "::" in key else key
                current_loc = objs[key]["fields"].get("location_id")
                if location_id != "0" and current_loc != location_id:
                    self._post({
                        "operation": "core/update",
                        "class": "StorageSystem",
                        "key": obj_id,
                        "fields": {"location_id": location_id}
                    })
                return obj_id
            
        res = self._post({
            "operation": "core/create",
            "class": "StorageSystem",
            "fields": {
                "name": name,
                "org_id": org_id,
                "location_id": location_id,
                "status": "production"
            }
        })
        objs = res.get("objects", {})
        if not objs: return "0"
        key = list(objs.keys())[0]
        return key.split("::")[1] if "::" in key else key

    def get_logical_volumes_for_storage(self, storage_id):
        body = self._post({
            "operation": "core/get",
            "class": "LogicalVolume",
            "key": f"SELECT LogicalVolume WHERE storagesystem_id = '{storage_id}'",
            "output_fields": "name,size,description,raid_level"
        })
        return body.get("objects") or {}

    def create_logical_volume(self, storage_id, name, size_gb, description, raid_level=""):
        res = self._post({
            "operation": "core/create",
            "class": "LogicalVolume",
            "fields": {
                "storagesystem_id": storage_id,
                "name": name,
                "size": str(size_gb),
                "description": description,
                "raid_level": raid_level,
                "lun_id": name.split(" ")[-1] if " " in name else "0"
            }
        })
        objs = res.get("objects", {})
        if not objs: return "0"
        key = list(objs.keys())[0]
        return key.split("::")[1] if "::" in key else key
        
    def update_logical_volume(self, volume_id, size_gb, description, raid_level=""):
        return self._post({
            "operation": "core/update",
            "class": "LogicalVolume",
            "key": volume_id,
            "fields": {
                "size": str(size_gb),
                "description": description,
                "raid_level": raid_level
            }
        })

    def link_server_to_volume(self, server_id, volume_id, size_gb=0):
        body = self._post({
            "operation": "core/get",
            "class": "lnkServerToVolume",
            "key": f"SELECT lnkServerToVolume WHERE server_id='{server_id}' AND volume_id='{volume_id}'",
            "output_fields": "id,size_used"
        })
        objs = body.get("objects", {})
        if not objs:
            self._post({
                "operation": "core/create",
                "class": "lnkServerToVolume",
                "fields": {
                    "server_id": server_id,
                    "volume_id": volume_id,
                    "size_used": str(size_gb)
                }
            })
            logger.info(f"    ↳ Created Link ServerToVolume: size_used={size_gb}")
        else:
            key = list(objs.keys())[0]
            obj_id = key.split("::")[1] if "::" in key else key
            current_size = objs[key]["fields"].get("size_used", "0")
            if str(current_size) != str(size_gb):
                self._post({
                    "operation": "core/update",
                    "class": "lnkServerToVolume",
                    "key": obj_id,
                    "fields": {
                        "size_used": str(size_gb)
                    }
                })
                logger.info(f"    ↳ Updated Link ServerToVolume: size_used={current_size} -> {size_gb}")






# ─── Redis Distributed Lock ───────────────────────────────────────────────────
def acquire_lock(uid: str) -> str:
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
def resolve_extra_fields(data: dict, class_name: str, ci_name: str, itop_client, org_id: str, hw_data: dict = None) -> dict:
    """
    Ekstrak field tambahan spesifik per tipe perangkat:
    - NetworkDevice: iosversion_id, networkdevicetype_id, location_id
    - Server: osfamily, osversion
    """
    raw_fields = data.get("raw_fields", {}) or {}
    raw_tags   = data.get("raw_tags", {}) or {}
    extra = {}
    
    # Generic Location & Rack mapping for all device classes
    loc_name = raw_tags.get("site") or raw_fields.get("location") or raw_fields.get("site")
    rack_name = raw_tags.get("rack_name") or raw_fields.get("rack_name")

    if hw_data:
        if not loc_name:
            loc_name = hw_data.get("site")
        if not rack_name:
            rack_name = hw_data.get("rack")

    if loc_name:
        loc_id = itop_client.get_or_create_location(loc_name, org_id)
        if loc_id and loc_id != "0":
            extra["location_id"] = loc_id
            if rack_name:
                rack_id = itop_client.get_or_create_rack(rack_name, loc_id, org_id)
                if rack_id and rack_id != "0":
                    extra["rack_id"] = rack_id

    if class_name == "NetworkDevice":
        # RAM dari memory_total_kb (hrMemorySize via SNMP, satuan KB)
        mem_total_kb = raw_fields.get("memory_total_kb")
        if mem_total_kb:
            try:
                ram_gb = int(mem_total_kb) // (1024 * 1024)
                ram_mb = int(mem_total_kb) // 1024
                if ram_gb >= 1:
                    extra["ram"] = f"{ram_gb} GB"
                elif ram_mb >= 1:
                    extra["ram"] = f"{ram_mb} MB"
            except (ValueError, TypeError):
                pass

        # 2. IOSVersion
        ios_ver = data.get("firmware") or raw_fields.get("ros_version") or raw_fields.get("firmware") or raw_tags.get("firmware") or raw_tags.get("firmware_version")
        if ios_ver:
            ios_id = itop_client.get_or_create_iosversion(str(ios_ver).strip())
            if ios_id and ios_id != "0":
                extra["iosversion_id"] = ios_id

        # 3. NetworkDeviceType
        device_type = str(data.get("device_type", "")).lower()
        ci_lower = ci_name.lower()
        type_str = ""
        
        if "ap-" in ci_lower or "-ap" in ci_lower or "-ap-" in ci_lower or "access point" in ci_lower:
            type_str = "Access Point"
        elif "sw-" in ci_lower or "-sw" in ci_lower or "-sw-" in ci_lower or "switch" in ci_lower:
            type_str = "Switch"
        elif "rtr-" in ci_lower or "-rtr" in ci_lower or "-rtr-" in ci_lower or "router" in ci_lower:
            type_str = "Router"
        elif "fw-" in ci_lower or "-fw" in ci_lower or "-fw-" in ci_lower or "firewall" in ci_lower:
            type_str = "Firewall"
        elif device_type in ("camera", "cctv"):
            type_str = "IP Camera"
        elif device_type == "nvr":
            type_str = "NVR"
        elif device_type == "network":
            # Jika "network" tapi punya modem di nama
            if "modem" in ci_lower:
                type_str = "Modem"
            elif "balancer" in ci_lower:
                type_str = "Load Balancer"

        if type_str:
            type_id = itop_client.get_or_create_networkdevicetype(type_str)
            if type_id and type_id != "0":
                extra["networkdevicetype_id"] = type_id

    elif class_name == "Server":
        # OS Family — simpan sebagai note untuk description (bukan FK "0" yang invalid)
        os_fam = (
            raw_tags.get("os") or
            raw_tags.get("os_name") or
            raw_fields.get("os_name") or
            raw_fields.get("oem_name")
        )
        if os_fam and str(os_fam).strip():
            extra["_osfamily_note"] = str(os_fam).strip()

        # OS Version / Firmware — simpan sebagai note untuk description
        os_ver = (
            raw_fields.get("firmware") or
            raw_fields.get("os_version") or
            raw_tags.get("firmware_version") or
            raw_fields.get("bios_version")
        )
        if os_ver and str(os_ver).strip():
            extra["_osversion_note"] = str(os_ver).strip()

    return extra


# ─── Main Message Processor ───────────────────────────────────────────────────

def sync_server_nics_and_disks(itop_client, server_id, hostname, org_id, location_id, hw_data, resolved_class="Server"):
    if not hw_data:
        return
        
    # 1. Sync NICs
    nic_comps = hw_data.get("nic_comps", [])
    if nic_comps:
        speed_map_mbps = {1: 10, 2: 100, 3: 1000, 4: 10000, 5: 40000, 6: 100000, 7: 25000}
        existing_nics = itop_client.get_network_interfaces(server_id)
        existing_macs = {v['fields'].get('macaddress', '').lower(): k for k, v in existing_nics.items()}
        
        for nic in nic_comps:
            mac = (nic.get("mac") or "").strip().lower()
            if not mac:
                continue
                
            label = nic.get("label", "NIC")
            speed_enum = nic.get("speed", 11)
            speed_mbps = speed_map_mbps.get(speed_enum, 0)
            ip = nic.get("ip_address", "")
            mask = nic.get("ip_mask", "")
            gateway = nic.get("ip_gateway", "")
            
            if mac in existing_macs:
                nic_id = existing_macs[mac]
                nic_data = next((v['fields'] for k, v in existing_nics.items() if (k.split("::")[1] if "::" in k else k) == nic_id.split("::")[-1]), {})
                if str(nic_data.get("speed")) != f"{speed_mbps}.00" or nic_data.get("ipaddress") != ip:
                    logger.info(f"  -> Updating NIC {label} for {hostname}")
                    itop_client.update_network_interface(nic_id.split("::")[-1] if "::" in nic_id else nic_id, label, speed_mbps, ip, mask, gateway)
            else:
                logger.info(f"  -> Creating NIC {label} ({mac}) for {hostname}")
                itop_client.create_network_interface(server_id, label, mac, speed_mbps, ip, mask, gateway)
                
    # 2. Sync Logical Volumes (Disks) — only for Server class, skip for NAS/NetworkDevice
    if resolved_class == "Server":
        disk_comps = hw_data.get("disk_comps", [])
        if not disk_comps:
            return  # No disks to sync
        
        storage_id = itop_client.get_or_create_local_storage_system(hostname, org_id, location_id)
        existing_vols = itop_client.get_logical_volumes_for_storage(storage_id)
        existing_vol_names = {v['fields'].get('name', ''): k.split("::")[1] if "::" in k else k for k, v in existing_vols.items()}
        
        for disk in disk_comps:
            slot = disk.get("slot", "")
            slot_str = str(slot).zfill(2) if str(slot).isdigit() else slot
            name = f"Slot {slot_str}" if slot else disk.get("model_name", "Drive")
            
            # disk from postgres has 'size' directly in GiB, or fallback to capacity_bytes calculation
            size_gb = disk.get("size", 0)
            if not size_gb and disk.get("capacity_bytes"):
                size_gb = int(disk.get("capacity_bytes") / (1024**3))
                
            raid_level = disk.get("raid_level", "")
            description = f"{disk.get('media_type', 'Unknown')} - {disk.get('protocol', 'Unknown')} - {disk.get('model_name', 'Drive')}"
            
            if name in existing_vol_names:
                vol_id = existing_vol_names[name]
                vol_data = next((v['fields'] for k, v in existing_vols.items() if (k.split("::")[1] if "::" in k else k) == vol_id), {})
                # Note: 'raid_level' internal name is assumed to be 'raid_level' based on screenshot fields
                if str(vol_data.get("size")) != str(size_gb) or vol_data.get("description") != description or vol_data.get("raid_level") != raid_level:
                    itop_client.update_logical_volume(vol_id, size_gb, description, raid_level)
            else:
                logger.info(f"  -> Creating Logical Volume {name} for {hostname}")
                vol_id = itop_client.create_logical_volume(storage_id, name, size_gb, description, raid_level)
                
            # Link ke server
            itop_client.link_server_to_volume(server_id, vol_id, size_gb)


def process_message(msg_val: str, itop_client: ITopClient, auto_org_id: str) -> str:
    import time
    t0 = time.time()
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
    
    # Log CCTV/camera events explicitly for debugging
    if device_type in ("camera", "cctv", "nvr"):
        logger.info(f"[CCTV] Received {device_type} event: hostname={hostname}, ip={ip}, serial={serial_number}, brand={brand_name}")

    ci_name = hostname
    loc_name = data.get("site", "")
    rack_name = data.get("rack_name", "")
    # Format generic camera hostnames — expand check to cover more variants
    if device_type in ("camera", "cctv"):
        hostname_upper = hostname.strip().upper()
        if hostname_upper in ("IP CAMERA", "CAMERA", "") and ip:
            ci_name = f"CAMERA-{ip.split('.')[-1]}"

    # Ensure SRV- is converted to SERVER- to match DB and Ralph
    if ci_name.upper().startswith("SRV-"):
        ci_name = "SERVER-" + ci_name[4:]

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

    # Dapatkan HW data untuk check perubahannya
    hw = None
    hw_hash = ""
    
    if device_type in ("server", "nas", ""):
        hw = get_server_hardware(ci_name)
    elif device_type in ("network", "network_switch", "nvr", "ups"):
        hw = get_network_hardware(ci_name, ip)
        
    if hw:
        if device_type in ("server", "nas", ""):
            # Re-inject ke msg agar bisa dihash dengan benar
            data["srv_cpu_components"] = hw.get("cpu_comps")
            data["srv_disk_components"] = hw.get("disk_comps")
            data["srv_memory_components"] = hw.get("mem_comps")
            hw_hash = str(data.get("srv_disk_components")) + str(data.get("srv_cpu_components")) + str(data.get("srv_memory_components"))
            import hashlib
            hw_hash = hashlib.md5(hw_hash.encode('utf-8')).hexdigest()
            
        loc_name = loc_name or hw.get("site", "")
        rack_name = rack_name or hw.get("rack", "")
        serial_number = serial_number or hw.get("serial_number", "")

    # Jika cache mengatakan CI sudah ada dengan data sama (termasuk hardware, lokasi, dan rack) → skip API call
    resolved_class = itop_client.resolve_class(device_type)
    if (cached_state.get("ip") == str(ip) and
        cached_state.get("status") == expected_status and
        cached_state.get("brand") == str(brand_name) and
        cached_state.get("name") == ci_name and
        cached_state.get("hw_hash") == hw_hash and
        cached_state.get("loc_name") == str(loc_name) and
        cached_state.get("rack_name") == str(rack_name)):
        
        measurement = data.get("measurement")
        if measurement != "interface":
            # Verify CI still exists in iTop (cache may be stale after manual delete)
            cached_obj_id = cached_state.get("obj_id")
            if cached_obj_id:
                verify_body = itop_client._post({
                    "operation": "core/get",
                    "class": resolved_class,
                    "key": cached_obj_id,
                    "output_fields": "id"
                })
                if not verify_body.get("objects"):
                    # CI was deleted from iTop but cache still valid → invalidate
                    logger.info(f"Cache stale for '{uid}' — CI {cached_obj_id} no longer exists, invalidating cache")
                    r_cache.delete(cache_key)
                    # Fall through to create logic below
                else:
                    return True
            else:
                return True
        else:
            # Interface event — cek cache per-interface (bukan per-device)
            if_name = raw_fields.get("if_name") or raw_fields.get("ifDescr")
            mac = str(raw_fields.get("ifPhysAddress", "")).lower()
            speed = raw_fields.get("ifSpeed", 0)
            speed_mbps = int(speed) // 1000000 if speed else 0
            
            # Gunakan if_name sebagai bagian dari key agar tiap interface punya cache sendiri
            if_cache_key = f"itop_if:{uid}:{if_name}"
            if_cached_state = r_cache.hgetall(if_cache_key)
            if (if_cached_state.get("mac") == mac and
                if_cached_state.get("speed") == str(speed_mbps)):
                return True
            # Cache belum ada / berubah → lanjut proses

    # ── Find Device in iTop ────────────────────────────────────────────────
    class_name, objs = itop_client.find_device(ci_name, serial_number, ip)

    if not objs:
        # CI tidak ada di iTop
        # Jika cache masih ada → berarti CI baru saja dihapus manual → invalidate cache
        if cached_state:
            logger.info(f"Cache invalidated for '{uid}' — CI dihapus dari iTop, akan dibuat ulang")
            r_cache.delete(cache_key)

        # Acquire distributed lock sebelum create (anti race-condition)
        lock_acquired = acquire_lock(uid)
        if not lock_acquired:
            logger.debug(f"Lock busy untuk '{uid}', proses lain sedang create — skip")
            return True  # Proses lain sedang handle, tidak perlu error

        try:
            # hw is already computed above before cache check
                
            extra_fields = resolve_extra_fields(data, resolved_class, ci_name, itop_client, auto_org_id, hw_data=hw)
            
            # Hardware enrichment for Servers
            if resolved_class == "Server" and hw:
                extra_fields.update({
                    "cpu": hw.get("cpu"),
                    "ram": hw.get("ram"),
                    "nb_u": hw.get("nb_u", "2")
                })

            elif resolved_class == "NetworkDevice":

                # nb_u default 1U untuk network device
                if "nb_u" not in extra_fields:
                    extra_fields["nb_u"] = "1"
                # RAM dari payload SNMP (memory_total_kb = hrMemorySize dalam KB)
                if "ram" not in extra_fields:
                    mem_total_kb = raw_fields.get("memory_total_kb")
                    if mem_total_kb:
                        try:
                            ram_gb = int(mem_total_kb) // (1024 * 1024)
                            ram_mb = int(mem_total_kb) // 1024
                            if ram_gb >= 1:
                                extra_fields["ram"] = f"{ram_gb} GB"
                            elif ram_mb >= 1:
                                extra_fields["ram"] = f"{ram_mb} MB"
                        except (ValueError, TypeError):
                            pass

            # Bangun description dengan OS info (jika ada)
            os_notes = []
            osf = extra_fields.pop("_osfamily_note", None)
            if osf:
                os_notes.append(f"OS: {osf}")
            osv = extra_fields.pop("_osversion_note", None)
            if osv:
                os_notes.append(f"Firmware/BIOS: {osv}")
            if os_notes:
                extra_fields["description"] = " | ".join(os_notes)

            created_id = itop_client.create_device(
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
            if created_id:
                logger.info(f"✨ Created {resolved_class} '{ci_name}' in iTop (ID={created_id})")
                if device_type in ("camera", "cctv", "nvr"):
                    logger.info(f"[CCTV] ✅ Successfully created {device_type} '{ci_name}' (SN={serial_number}, IP={ip}) as {resolved_class}")
                # Sinkronisasi NIC & Logical Volumes jika Server / NAS
                if resolved_class in ("Server", "NAS") and hw and created_id != "created":
                    loc = extra_fields.get("location_id", "0")
                    sync_server_nics_and_disks(itop_client, created_id, ci_name, auto_org_id, loc, hw, resolved_class)
                
                r_cache.hset(cache_key, mapping={
                    "ip": str(ip), "status": expected_status, "brand": str(brand_name), "name": ci_name,
                    "loc_name": str(loc_name or (hw.get("site", "") if hw else "")), 
                    "rack_name": str(rack_name or (hw.get("rack", "") if hw else "")),
                    "obj_id": str(created_id) if created_id and created_id != "created" else ""
                })
                r_cache.expire(cache_key, CACHE_TTL)
                return True
            if device_type in ("camera", "cctv", "nvr"):
                logger.error(f"[CCTV] ❌ FAILED to create {device_type} '{ci_name}' (SN={serial_number}, IP={ip}) — check iTop API logs above")
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
    if ip and class_name not in ("PowerConnection", "PowerSource", "Peripheral") and str(ip) != str(current_ip):
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
        fields_to_update["serialnumber"] = serial_number

    # Enrich asset_number jika masih kosong (pakai serial sebagai fallback)
    if serial_number and class_name in ("Server", "NetworkDevice", "StorageSystem", "NAS", "PowerSource"):
        if not obj_fields.get("asset_number"):
            fields_to_update["asset_number"] = serial_number

    # ios_version di iTop adalah FK (iosversion_id) — skip update otomatis

    # Update name jika sebelumnya "IP CAMERA" generic dan ci_name baru telah dikalkulasi
    current_name = obj_fields.get("name", "")
    if current_name != ci_name:
        fields_to_update["name"] = ci_name

    # Auto-fill missing extra fields for NetworkDevice and Server
    # hw is already computed above

    extra_fields = resolve_extra_fields(data, class_name, ci_name, itop_client, auto_org_id, hw_data=hw)
    if extra_fields:
        for k, v in extra_fields.items():
            if not k.startswith("_"):
                current_val = obj_fields.get(k)
                # Location and rack should always update if changed. Other fields only auto-fill if empty.
                if k in ("location_id", "rack_id"):
                    if current_val != v:
                        fields_to_update[k] = v
                else:
                    if current_val != v and (not current_val or current_val == "0"):
                        fields_to_update[k] = v

    # Auto-fill missing hardware fields for Server
    if class_name == "Server":
        if hw:
            if hw.get("cpu") and not obj_fields.get("cpu"): fields_to_update["cpu"] = hw["cpu"]
            if hw.get("ram") and not obj_fields.get("ram"): fields_to_update["ram"] = hw["ram"]
            if hw.get("nb_u") and not obj_fields.get("nb_u"): fields_to_update["nb_u"] = hw.get("nb_u", "2")

    # Auto-fill missing hardware fields for NetworkDevice
    if class_name == "NetworkDevice":
        if hw:
            if not obj_fields.get("nb_u"): fields_to_update["nb_u"] = "1"
            if not obj_fields.get("ram"):
                # Baca dari SNMP payload jika tersedia
                mem_total_kb = raw_fields.get("memory_total_kb")
                if mem_total_kb:
                    try:
                        ram_gb = int(mem_total_kb) // (1024 * 1024)
                        ram_mb = int(mem_total_kb) // 1024
                        if ram_gb >= 1:
                            fields_to_update["ram"] = f"{ram_gb} GB"
                        elif ram_mb >= 1:
                            fields_to_update["ram"] = f"{ram_mb} MB"
                    except (ValueError, TypeError):
                        pass

    # Sinkronisasi hardware hanya jika hw_hash berubah (bukan saat location berubah)
    if hw and str(cached_state.get("hw_hash")) != str(hw_hash):
        if class_name in ("Server", "NAS"):
            loc = fields_to_update.get("location_id", obj_fields.get("location_id", "0"))
            sync_server_nics_and_disks(itop_client, obj_id, ci_name, auto_org_id, loc, hw, class_name)
        r_cache.hset(cache_key, "hw_hash", hw_hash)

    # Always ensure StorageSystem location matches Server location (even if hw_hash unchanged)
    if class_name == "Server":
        server_loc = fields_to_update.get("location_id", obj_fields.get("location_id", "0"))
        if server_loc and server_loc != "0":
            storage_name = f"Local Storage - {ci_name}"
            storage_objs = itop_client._post({
                "operation": "core/get", "class": "StorageSystem",
                "key": f"SELECT StorageSystem WHERE name = '{storage_name}'",
                "output_fields": "id,location_id"
            }).get("objects", {})
            if storage_objs:
                s_key = list(storage_objs.keys())[0]
                s_id = s_key.split("::")[1] if "::" in s_key else s_key
                s_loc = storage_objs[s_key]["fields"].get("location_id")
                if str(s_loc) != str(server_loc):
                    logger.info(f"  -> Updating StorageSystem '{storage_name}' location: {s_loc} → {server_loc}")
                    itop_client._post({
                        "operation": "core/update", "class": "StorageSystem",
                        "key": s_id, "fields": {"location_id": server_loc},
                        "comment": "Auto-synced server location by dcim-itop-consumer v8"
                    })

    # Sinkronisasi network interface untuk router/switch dan NAS
    measurement = data.get("measurement")
    if measurement == "interface" and obj_id:
        # Process interface for NetworkDevice and NAS classes
        if class_name in ("NetworkDevice", "NAS"):
            if_name = raw_fields.get("if_name") or raw_fields.get("ifDescr")
            mac = raw_fields.get("ifPhysAddress", "")
            speed = raw_fields.get("ifSpeed", 0)
            speed_mbps = int(speed) // 1000000 if speed else 0
            if if_name:
                existing_nics = itop_client.get_network_interfaces(obj_id)
                existing_names = {v['fields'].get('name', '').lower(): k for k, v in existing_nics.items()}
                
                if if_name.lower() in existing_names:
                    nic_key = existing_names[if_name.lower()]
                    nic_id = nic_key.split("::")[-1]
                    nic_data = next((v['fields'] for k, v in existing_nics.items() if k == nic_key), {})
                    # update if mac or speed differ
                    if str(nic_data.get("macaddress")).lower() != mac.lower() or str(nic_data.get("speed", "0")).split('.')[0] != str(speed_mbps):
                        logger.info(f"  -> Updating interface {if_name} ({mac}) for {ci_name}")
                        itop_client.update_network_interface(nic_id, if_name, speed_mbps, mac=mac)
                else:
                    logger.info(f"  -> Creating interface {if_name} ({mac}) for {ci_name}")
                    itop_client.create_network_interface(obj_id, if_name, mac, speed_mbps)
                    
                if_cache_key = f"itop_if:{uid}:{if_name}"
                r_cache.hset(if_cache_key, mapping={"mac": str(mac).lower(), "speed": str(speed_mbps)})
                r_cache.expire(if_cache_key, CACHE_TTL)

    if not fields_to_update:
        # Tidak ada yang berubah → update cache saja
        # Use resolved location for cache
        resolved_loc = loc_name
        resolved_rack = rack_name
        if hw:
            resolved_loc = resolved_loc or hw.get("site", "")
            resolved_rack = resolved_rack or hw.get("rack", "")
        r_cache.hset(cache_key, mapping={
            "ip": str(ip), "status": expected_status, "brand": str(brand_name), "name": ci_name, "hw_hash": hw_hash,
            "loc_name": str(resolved_loc), "rack_name": str(resolved_rack), "obj_id": str(obj_id)
        })
        r_cache.expire(cache_key, CACHE_TTL)
        if time.time() - t0 > 5:
            logger.warning(f"[SLOW] process_message took {time.time() - t0:.2f}s for {ci_name} (no fields to update)")
        return True

    logger.info(f"↺ Updating {class_name} '{ci_name}' (ID={obj_id}): {list(fields_to_update.keys())}")
    success = itop_client.update_device(class_name, obj_id, fields_to_update)

    if success:
        # Use resolved location for cache (not raw Kafka data which may be empty)
        resolved_loc = loc_name
        resolved_rack = rack_name
        if hw:
            resolved_loc = resolved_loc or hw.get("site", "")
            resolved_rack = resolved_rack or hw.get("rack", "")
        r_cache.hset(cache_key, mapping={
            "ip": str(ip), "status": expected_status, "brand": str(brand_name), "name": ci_name, "hw_hash": hw_hash,
            "loc_name": str(resolved_loc), "rack_name": str(resolved_rack), "obj_id": str(obj_id)
        })
        r_cache.expire(cache_key, CACHE_TTL)
        return True
    if time.time() - t0 > 5:
        logger.warning(f"[SLOW] process_message took {time.time() - t0:.2f}s for {ci_name} (updated)")
    return False


# ─── DLQ Producer ─────────────────────────────────────────────────────────────
def produce_dlq(producer, topic: str, event_data: dict, error_msg: str):
    event_data["error_reason"] = error_msg
    producer.produce(topic, value=json.dumps(event_data).encode("utf-8"))
    producer.flush(timeout=5)
    logger.error(f"→ DLQ: {error_msg}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    conf = {
        'bootstrap.servers':      KAFKA_BROKERS,
        'group.id':               'dcim_itop_group_v8',
        'auto.offset.reset':      'latest',
        'enable.auto.commit':     True,
        'max.poll.interval.ms':   600000,  # 10 menit — cegah group leave saat proses API iTop lama
        'session.timeout.ms':     30000,   # 30 detik
        'heartbeat.interval.ms':  10000,   # 10 detik
    }
    consumer = Consumer(conf)
    consumer.subscribe([TOPIC_IN])

    prod_conf = {'bootstrap.servers': KAFKA_BROKERS}
    producer  = Producer(prod_conf)

    itop_client  = ITopClient()
    auto_org_id  = itop_client.get_target_org_id()

    logger.info(f"✓ dcim-itop-consumer v8 started | topic={TOPIC_IN} | group=dcim_itop_group_v8 | org_id={auto_org_id}")

    try:
        while True:
            # Gunakan consume() agar librdkafka tetap mengirim heartbeat saat process_message() berjalan
            msgs = consumer.consume(num_messages=1, timeout=1.0)
            if not msgs:
                continue

            msg = msgs[0]
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
