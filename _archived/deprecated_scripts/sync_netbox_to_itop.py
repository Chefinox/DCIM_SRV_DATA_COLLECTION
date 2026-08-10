#!/usr/bin/env python3
"""Idempotent NetBox to iTop CMDB synchronizer."""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml
from prometheus_client import Counter, Gauge, generate_latest
from pythonjsonlogger import jsonlogger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

SYNC_OBJECTS = Counter("netbox_itop_sync_objects_total", "Objects processed", ["kind", "status"])
SYNC_ERRORS = Counter("netbox_itop_sync_errors_total", "Sync errors", ["stage"])
LAST_SUCCESS = Gauge("netbox_itop_sync_last_success_timestamp", "Last successful sync timestamp")
LAST_RUN_STATUS = Gauge("netbox_itop_sync_last_run_status", "Last run status: 1 success, 0 failure")

STOP = threading.Event()


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


LOG = logging.getLogger("netbox_itop_sync")


@dataclass
class Settings:
    netbox_url: str
    netbox_token: str
    itop_url: str
    itop_user: str
    itop_password: str
    state_file: Path
    interval: int
    mapping_file: Path
    dry_run: bool = False

    @classmethod
    def from_env(cls, mapping_file: str, dry_run: bool) -> "Settings":
        required = ["NETBOX_TOKEN", "ITOP_USER", "ITOP_PASSWORD"]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            netbox_url=os.getenv("NETBOX_URL", "http://10.70.0.20:9008/"),
            netbox_token=os.environ["NETBOX_TOKEN"],
            itop_url=os.getenv("ITOP_URL", "http://localhost:8080"),
            itop_user=os.environ["ITOP_USER"],
            itop_password=os.environ["ITOP_PASSWORD"],
            state_file=Path(os.getenv("SYNC_STATE_FILE", "./netbox_itop_state.json")),
            interval=int(os.getenv("SYNC_INTERVAL_SECONDS", "3600")),
            mapping_file=Path(mapping_file),
            dry_run=dry_run,
        )


class NetBoxClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Token {token}", "Accept": "application/json"})

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20), retry=retry_if_exception_type(requests.RequestException))
    def get_page(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else urljoin(self.base_url, path_or_url.lstrip("/"))
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def list_all(self, path: str, since: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": 200}
        if since:
            params["last_updated__gte"] = since
        data = self.get_page(path, params)
        results = list(data.get("results", []))
        next_url = data.get("next")
        while next_url:
            data = self.get_page(next_url)
            results.extend(data.get("results", []))
            next_url = data.get("next")
        return results


class ITopClient:
    def __init__(self, base_url: str, user: str, password: str, dry_run: bool) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.user = user
        self.password = password
        self.dry_run = dry_run
        self.session = requests.Session()

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20), retry=retry_if_exception_type(requests.RequestException))
    def core(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.dry_run and payload.get("operation") in {"core/create", "core/update"}:
            LOG.info("dry_run_skip_itop_write", extra={"operation": payload.get("operation"), "class": payload.get("class")})
            return {"code": 0, "message": "dry-run", "objects": {}}
        response = self.session.post(
            urljoin(self.base_url, "webservices/rest.php?version=1.3"),
            data={"auth_user": self.user, "auth_pwd": self.password, "json_data": json.dumps(payload)},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") not in (0, None):
            raise RuntimeError(f"iTop API error: {body}")
        return body

    def find(self, class_name: str, key_field: str, key_value: str) -> tuple[str | None, dict[str, Any] | None]:
        oql_value = str(key_value).replace("'", "\\'")
        query = f"SELECT {class_name} WHERE {key_field} = '{oql_value}'"
        body = self.core({"operation": "core/get", "class": class_name, "key": query, "output_fields": "*"})
        objects = body.get("objects") or {}
        if len(objects) > 1:
            raise RuntimeError(f"Duplicate iTop objects class={class_name} {key_field}={key_value}")
        if not objects:
            return None, None
        object_id, payload = next(iter(objects.items()))
        return object_id.split("::")[-1], payload.get("fields", {})

    def upsert(self, class_name: str, key_field: str, key_value: str, fields: dict[str, Any]) -> str | None:
        object_id, current = self.find(class_name, key_field, key_value)
        fields = {k: v for k, v in fields.items() if v not in (None, "")}
        if object_id:
            if current and all(str(current.get(k, "")) == str(v) for k, v in fields.items()):
                return object_id
            self.core({"operation": "core/update", "class": class_name, "key": object_id, "fields": fields, "comment": "NetBox sync update"})
            return object_id
        body = self.core({"operation": "core/create", "class": class_name, "fields": fields, "comment": "NetBox sync create"})
        objects = body.get("objects") or {}
        if objects:
            return next(iter(objects.keys())).split("::")[-1]
        return None


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        if path.exists():
            self.data = json.loads(path.read_text())

    def get_since(self) -> str | None:
        return self.data.get("last_successful_started_at")

    def commit(self, started_at: str, failures: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = {"last_successful_started_at": started_at, "last_completed_at": utc_now(), "failures": failures[-200:]}
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True))


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean_name(*values: Any) -> str:
    for value in values:
        if value:
            return str(value).strip()
    return "unnamed"


def ref_name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name") or value.get("display") or value.get("slug")
    return None


def role_class(device: dict[str, Any], mapping: dict[str, Any]) -> str:
    role = (ref_name(device.get("role")) or ref_name(device.get("device_role")) or "default").lower()
    role_map = mapping.get("role_to_itop_class", {})
    for token, class_name in role_map.items():
        if token in role:
            return class_name
    return role_map.get("default", "PhysicalDevice")

def model_name(device_type: dict[str, Any]) -> str | None:
    if isinstance(device_type, dict):
        return device_type.get("model") or device_type.get("display") or device_type.get("name")
    return None


def load_mapping(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


class Synchronizer:
    def __init__(self, settings: Settings, mapping: dict[str, Any]) -> None:
        self.settings = settings
        self.mapping = mapping
        self.netbox = NetBoxClient(settings.netbox_url, settings.netbox_token)
        self.itop = ITopClient(settings.itop_url, settings.itop_user, settings.itop_password, settings.dry_run)
        self.state = StateStore(settings.state_file)
        self.ids: dict[str, dict[int, str]] = {k: {} for k in ["sites", "racks", "manufacturers", "devices", "interfaces", "ips", "vms", "clusters", "vm_hosts"]}
        self.location_ids: dict[str, str] = {}
        self.failures: list[dict[str, Any]] = []
        self.org_id = str(self.mapping.get("defaults", {}).get("organization_id", "1"))
        self.network_device_type_id: str | None = None

    def sync(self) -> None:
        started_at = utc_now()
        endpoints = self.mapping["endpoints"]
        since = self.state.get_since()
        LOG.info("sync_started", extra={"since": since, "dry_run": self.settings.dry_run})
        data = {name: self.netbox.list_all(path, since=None if name in {"sites", "racks", "manufacturers", "device_types", "device_roles"} else since) for name, path in endpoints.items() if name != "cables"}
        self.ensure_reference_data()
        self.sync_manufacturers(data.get("manufacturers", []))
        self.sync_sites(data.get("sites", []))
        self.sync_device_locations(data.get("devices", []))
        self.sync_racks(data.get("racks", []))
        self.sync_devices(data.get("devices", []))
        if self.mapping.get("sync", {}).get("vm_cluster_hosts", False):
            self.sync_vm_cluster_hosts(data.get("clusters", []))
        if self.mapping.get("sync", {}).get("clusters", False):
            self.sync_clusters(data.get("clusters", []))
        if self.mapping.get("sync", {}).get("virtual_machines", False):
            self.sync_vms(data.get("virtual_machines", []))
        if self.mapping.get("sync", {}).get("interfaces", False):
            self.sync_interfaces(data.get("interfaces", []), owner_type="device")
            self.sync_interfaces(data.get("vm_interfaces", []), owner_type="vm")
        if self.mapping.get("sync", {}).get("ip_addresses", False):
            self.sync_ips(data.get("ip_addresses", []))
        self.validate_relationships()
        if self.failures:
            LAST_RUN_STATUS.set(0)
            SYNC_ERRORS.labels(stage="object_failures").inc(len(self.failures))
            LOG.error("sync_completed_with_failures", extra={"failure_count": len(self.failures)})
        else:
            LAST_RUN_STATUS.set(1)
            LAST_SUCCESS.set(time.time())
            self.state.commit(started_at, self.failures)
            LOG.info("sync_completed", extra={"started_at": started_at})

    def safe(self, kind: str, item: dict[str, Any], func) -> None:
        try:
            func(item)
            SYNC_OBJECTS.labels(kind=kind, status="success").inc()
        except Exception as exc:
            SYNC_OBJECTS.labels(kind=kind, status="failed").inc()
            failure = {"kind": kind, "id": item.get("id"), "object_name": item.get("name") or item.get("display"), "error": str(exc)}
            self.failures.append(failure)
            LOG.exception("object_sync_failed", extra=failure)

    def key_field(self, class_name: str) -> str:
        return self.mapping.get("uniqueness", {}).get(class_name, "name")

    def upsert(self, class_name: str, unique_value: str, fields: dict[str, Any]) -> str | None:
        return self.itop.upsert(class_name, self.key_field(class_name), unique_value, fields)

    def ensure_reference_data(self) -> None:
        type_name = self.mapping.get("defaults", {}).get("network_device_type", "Generic")
        self.network_device_type_id = self.upsert("NetworkDeviceType", type_name, {"name": type_name})

    def sync_manufacturers(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            self.safe("manufacturer", item, lambda x: self.ids["manufacturers"].__setitem__(x["id"], self.upsert("Brand", clean_name(x.get("name")), {"name": clean_name(x.get("name"))}) or ""))

    def sync_sites(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                name = clean_name(x.get("name"), x.get("slug"))
                fields = {"name": name, "org_id": self.org_id, "status": "active"}
                self.ids["sites"][x["id"]] = self.upsert("Location", name, fields) or ""
            self.safe("site", item, do)

    def sync_device_locations(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            location = item.get("location") if isinstance(item.get("location"), dict) else None
            site = item.get("site") if isinstance(item.get("site"), dict) else None
            name = clean_name(location.get("name") if location else None, site.get("name") if site else None)
            if not name or name == "unnamed" or name in self.location_ids:
                continue
            fields = {"name": name, "org_id": self.org_id, "status": "active"}
            location_id = self.upsert("Location", name, fields)
            if location_id:
                self.location_ids[name] = location_id

    def sync_model(self, class_name: str, name: str | None, brand_id: str | None) -> str | None:
        if not name or not brand_id:
            return None
        fields = {"name": name, "brand_id": brand_id, "type": class_name}
        return self.upsert("Model", name, fields)

    def sync_racks(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                name = clean_name(x.get("name"), x.get("display"))
                site_id = x.get("site", {}).get("id") if isinstance(x.get("site"), dict) else None
                fields = {"name": name, "org_id": self.org_id, "description": x.get("description") or f"NetBox rack {x.get('id')}", "location_id": self.ids["sites"].get(site_id)}
                self.ids["racks"][x["id"]] = self.upsert("Rack", name, fields) or ""
            self.safe("rack", item, do)

    def sync_devices(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                name = clean_name(x.get("name"), x.get("display"))
                class_name = role_class(x, self.mapping)
                rack_id = x.get("rack", {}).get("id") if isinstance(x.get("rack"), dict) else None
                manufacturer_id = None
                dtype = x.get("device_type") if isinstance(x.get("device_type"), dict) else {}
                manufacturer = dtype.get("manufacturer") if isinstance(dtype, dict) else None
                if isinstance(manufacturer, dict):
                    manufacturer_id = self.ids["manufacturers"].get(manufacturer.get("id"))
                model_id = self.sync_model(class_name, model_name(dtype), manufacturer_id)
                location = x.get("location") if isinstance(x.get("location"), dict) else None
                site = x.get("site") if isinstance(x.get("site"), dict) else None
                location_name = clean_name(location.get("name") if location else None, site.get("name") if site else None)
                fields = {
                    "name": name,
                    "org_id": self.org_id,
                    "serialnumber": x.get("serial"),
                    "description": x.get("comments") or x.get("description") or f"NetBox device {x.get('id')}",
                    "brand_id": manufacturer_id,
                    "model_id": model_id,
                    "location_id": self.location_ids.get(location_name) or self.ids["sites"].get(site.get("id") if site else None),
                }
                if class_name in {"Server", "Hypervisor", "NAS", "NetworkDevice"}:
                    fields["rack_id"] = self.ids["racks"].get(rack_id)
                if class_name == "NetworkDevice":
                    fields["networkdevicetype_id"] = self.network_device_type_id
                self.ids["devices"][x["id"]] = self.upsert(class_name, name, fields) or ""
            self.safe("device", item, do)

    def sync_clusters(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            self.safe("cluster", item, lambda x: self.ids["clusters"].__setitem__(x["id"], self.upsert("LogicalVolume", clean_name(x.get("name")), {"name": clean_name(x.get("name")), "org_id": self.org_id, "description": f"NetBox cluster {x.get('id')}"}) or ""))

    def sync_vm_cluster_hosts(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                name = clean_name(x.get("name"), x.get("display"))
                fields = {"name": name, "org_id": self.org_id, "description": x.get("description") or f"NetBox cluster {x.get('id')}"}
                self.ids["vm_hosts"][x["id"]] = self.upsert("Hypervisor", name, fields) or ""
            self.safe("vm_host", item, do)

    def sync_vms(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                name = clean_name(x.get("name"), x.get("display"))
                host_id = None
                device = x.get("device") if isinstance(x.get("device"), dict) else None
                if device:
                    host_id = self.ids["devices"].get(device.get("id"))
                cluster = x.get("cluster") if isinstance(x.get("cluster"), dict) else None
                if not host_id and cluster:
                    host_id = self.ids["vm_hosts"].get(cluster.get("id"))
                if not host_id:
                    LOG.warning("vm_skipped_missing_host", extra={"vm_id": x.get("id"), "vm_name": name})
                    return
                description_parts = [x.get("comments") or f"NetBox VM {x.get('id')}"]
                if x.get("vcpus") is not None:
                    description_parts.append(f"vCPUs: {x.get('vcpus')}")
                if x.get("memory") is not None:
                    description_parts.append(f"Memory MB: {x.get('memory')}")
                if x.get("disk") is not None:
                    description_parts.append(f"Disk MB: {x.get('disk')}")
                fields = {"name": name, "org_id": self.org_id, "description": " | ".join(description_parts), "virtualhost_id": host_id}
                self.ids["vms"][x["id"]] = self.upsert("VirtualMachine", name, fields) or ""
            self.safe("vm", item, do)

    def sync_interfaces(self, items: list[dict[str, Any]], owner_type: str) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                owner = x.get("device") if owner_type == "device" else x.get("virtual_machine")
                owner_id = owner.get("id") if isinstance(owner, dict) else None
                connectable_id = self.ids["devices"].get(owner_id) if owner_type == "device" else self.ids["vms"].get(owner_id)
                name = f"{clean_name(ref_name(owner), owner_id)}:{clean_name(x.get('name'))}"
                fields = {"name": name, "connectableci_id": connectable_id, "description": f"NetBox interface {x.get('id')}"}
                self.ids["interfaces"][x["id"]] = self.upsert("NetworkInterface", name, fields) or ""
            self.safe("interface", item, do)

    def sync_ips(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            def do(x: dict[str, Any]) -> None:
                addr = str(ipaddress.ip_interface(x["address"]).ip)
                assigned = x.get("assigned_object") if isinstance(x.get("assigned_object"), dict) else None
                interface_id = self.ids["interfaces"].get(assigned.get("id")) if assigned else None
                fields = {"ip": addr, "short_name": addr, "ipinterface_id": interface_id, "comment": f"NetBox IP {x.get('id')}"}
                self.ids["ips"][x["id"]] = self.upsert("IPAddress", addr, fields) or ""
            self.safe("ip", item, do)

    def validate_relationships(self) -> None:
        missing = [failure for failure in self.failures if "Duplicate" in failure.get("error", "")]
        if missing:
            raise RuntimeError(f"Duplicate CI validation failed: {missing[:5]}")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/metrics":
            body = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_health_server() -> ThreadingHTTPServer:
    host = os.getenv("HEALTHCHECK_HOST", "127.0.0.1")
    port = int(os.getenv("HEALTHCHECK_PORT", "8088"))
    server = ThreadingHTTPServer((host, port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    LOG.info("health_server_started", extra={"host": host, "port": port})
    return server


def run_once(settings: Settings) -> int:
    mapping = load_mapping(settings.mapping_file)
    try:
        Synchronizer(settings, mapping).sync()
        return 0
    except Exception:
        LAST_RUN_STATUS.set(0)
        SYNC_ERRORS.labels(stage="sync_run").inc()
        LOG.exception("sync_failed")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync NetBox data into iTop CMDB")
    parser.add_argument("--mapping", default="mapping.yaml")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    setup_logging(os.getenv("LOG_LEVEL", "INFO"))
    settings = Settings.from_env(args.mapping, args.dry_run)
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    if args.daemon:
        server = start_health_server()
        try:
            while not STOP.is_set():
                run_once(settings)
                STOP.wait(settings.interval)
        finally:
            server.shutdown()
        return 0
    return run_once(settings)


if __name__ == "__main__":
    sys.exit(main())
