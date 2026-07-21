#!/usr/bin/env python3
import sys
import json
import os
import time
import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET

# Standalone CCTV/NVR Poller for NiFi ExecuteProcess


def _read_secret(name, env_var, fallback=None):
    """
    Read secret following DCIM-Wiki standard priority:
      1. HashiCorp Vault (AppRole auth via hvac)
      2. Docker secret file at /run/secrets/dcim/{name}
      3. Environment variable
      4. Hardcoded fallback (last resort, deprecated)
    """
    # --- 1. Try Vault via AppRole ---
    try:
        import hvac

        vault_addr = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
        role_id_path = os.environ.get(
            'VAULT_ROLE_ID_PATH',
            '/home/infra/dcim_metrics_project/vault/config/role_id'
        )
        secret_id_path = os.environ.get(
            'VAULT_SECRET_ID_PATH',
            '/home/infra/dcim_metrics_project/vault/config/secret_id'
        )

        if os.path.isfile(role_id_path) and os.path.isfile(secret_id_path):
            with open(role_id_path, 'r') as f:
                role_id = f.read().strip()
            with open(secret_id_path, 'r') as f:
                secret_id = f.read().strip()

            client = hvac.Client(url=vault_addr)
            client.auth.approle.login(role_id=role_id, secret_id=secret_id)

            read_response = client.secrets.kv.v2.read_secret_version(
                mount_point='secret',
                path=f'dcim/{name}',
                raise_on_deleted_version=False
            )
            secret_data = read_response['data']['data']
            if 'password' in secret_data:
                return secret_data['password']
            elif 'token' in secret_data:
                return secret_data['token']
            else:
                return list(secret_data.values())[0]
    except (ImportError, Exception):
        pass  # Vault not available, fall through

    # --- 2. Try Docker secret file (NiFi mounts at /run/secrets/<name>) ---
    for secret_base in ('/run/secrets/dcim', '/run/secrets'):
        docker_secret_path = f'{secret_base}/{name}'
        if os.path.isfile(docker_secret_path):
            try:
                with open(docker_secret_path, 'r') as f:
                    val = f.read().strip()
                    if val:
                        return val
            except OSError:
                pass

    # --- 3. Try environment variable ---
    val = os.environ.get(env_var)
    if val:
        return val

    # --- 4. Hardcoded fallback (deprecated per MT-018) ---
    return fallback


NVR_IP = os.environ.get("NVR_IP", "192.168.1.254")
CCTV_IPS = [
    "192.168.1.2", "192.168.1.3", "192.168.1.4", "192.168.1.5", "192.168.1.6",
    "192.168.1.7", "192.168.1.8", "192.168.1.9", "192.168.1.10", "192.168.1.11",
    "192.168.1.12", "192.168.1.13", "192.168.1.14", "192.168.1.15", "192.168.1.16",
    "192.168.1.17", "192.168.1.18", "192.168.1.19", "192.168.1.20", "192.168.1.21",
    "192.168.1.22", "192.168.1.23", "192.168.1.24", "192.168.1.25", "192.168.1.26",
    "192.168.1.27", "192.168.1.28", "192.168.1.29", "192.168.1.30", "192.168.1.31",
    "192.168.1.33"
]

DEVICE_USER = os.environ.get("HIKVISION_CAM_USER", "admin")
DEVICE_PASS = _read_secret("hikvision_cam_pass", "HIKVISION_CAM_PASS")
NVR_USER = os.environ.get("HIKVISION_NVR_USER", "admin")
NVR_PASS = _read_secret("hikvision_nvr_pass", "HIKVISION_NVR_PASS")
TIMEOUT = int(os.environ.get("ISAPI_TIMEOUT", "4"))

def get_isapi(ip, user, password, path):
    url = f"http://{ip}/ISAPI{path}"
    try:
        resp = requests.get(url, auth=HTTPDigestAuth(user, password), timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None

def get_xml_text(root, tag_name):
    if root is None: return None
    for elem in root.iter():
        if tag_name in elem.tag:
            return elem.text
    return None

def poll_device(ip, user, password, category, ts):
    xml_str = get_isapi(ip, user, password, "/System/deviceInfo")
    if not xml_str:
        return {
            "name": "cctv_metrics",
            "tags": {
                "hostname": f"CCTV-{ip.replace('.', '-')}",
                "serial_number": f"CCTV-IP-{ip.replace('.', '-')}",
                "ip": ip,
                "model": "DS-2CD",
                "manufacturer": "Hikvision",
                "device_type": category.lower()
            },
            "fields": {
                "status_online": 0,
                "status_text": "Offline"
            },
            "timestamp": ts
        }

    try:
        root = ET.fromstring(xml_str)
    except Exception:
        root = None

    hostname = get_xml_text(root, "deviceName") or f"CCTV-{ip.replace('.', '-')}"
    serial = get_xml_text(root, "serialNumber") or f"CCTV-IP-{ip.replace('.', '-')}"
    model = get_xml_text(root, "model") or "DS-2CD"
    manufacturer = get_xml_text(root, "manufacturer") or "Hikvision"

    tags = {
        "hostname": hostname,
        "serial_number": serial,
        "ip": ip,
        "model": model,
        "manufacturer": manufacturer,
        "device_type": category.lower()
    }
    
    fields = {
        "status_online": 1,
        "status_text": "Online"
    }

    # memory/cpu info
    status_xml = get_isapi(ip, user, password, "/System/status")
    if status_xml:
        try:
            s_root = ET.fromstring(status_xml)
            cpu = get_xml_text(s_root, "cpuUtilization")
            mem = get_xml_text(s_root, "memoryUsage")
            mem_avail = get_xml_text(s_root, "memoryAvailable")
            if cpu: fields["cpuUtilization"] = float(cpu)
            if mem: fields["memoryUsage"] = float(mem)
            if mem_avail: fields["memoryAvailable"] = float(mem_avail)
            
            if mem and mem_avail:
                used = float(mem)
                avail = float(mem_avail)
                total = used + avail
                if total > 0:
                    fields["memoryUsagePct"] = (used / total) * 100
        except Exception:
            pass

    return {
        "name": "cctv_metrics",
        "tags": tags,
        "fields": fields,
        "timestamp": ts
    }

def discover_nvr_channels():
    mapping = {}
    xml_str = get_isapi(NVR_IP, NVR_USER, NVR_PASS, "/ContentMgmt/InputProxy/channels")
    if xml_str:
        try:
            root = ET.fromstring(xml_str)
            for ch in root.iter():
                if "InputProxyChannel" in ch.tag and "InputProxyChannelStatus" not in ch.tag:
                    ip = get_xml_text(ch, "ipAddress")
                    sn = get_xml_text(ch, "serialNumber")
                    if ip and sn:
                        mapping[ip] = sn
        except Exception:
            pass
    return mapping

def main():
    ts = int(time.time())
    
    # Poll NVR
    nvr = poll_device(NVR_IP, NVR_USER, NVR_PASS, "NVR", ts)
    print(json.dumps(nvr))
    
    # Discover NVR channels for serial number fallback
    nvr_mapping = discover_nvr_channels()
    
    # Poll Cameras
    for ip in CCTV_IPS:
        cam = poll_device(ip, DEVICE_USER, DEVICE_PASS, "CCTV", ts)
        
        # fallback serial if offline
        if cam["fields"]["status_online"] == 0 and ip in nvr_mapping:
            cam["tags"]["serial_number"] = nvr_mapping[ip]
            
        print(json.dumps(cam))

if __name__ == "__main__":
    main()
