import requests
import xml.etree.ElementTree as ET
import json
import urllib3
import re
urllib3.disable_warnings()

# ─── Config ──────────────────────────────────────────────────
ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER = "admin"
ITOP_PASS = "Inovasi@0918"

NVR_IP = "192.168.1.254"
NVR_USER = "admin"
NVR_PASS = "qRvbi883=Zk[Q)@5"

# Expected targets
CCTV_TARGETS = {
    "192.168.1.2": "R. Content 2 View2",
    "192.168.1.3": "R. Content 2 View1",
    "192.168.1.4": "Koridor Mess Lt.2",
    "192.168.1.5": "R. Server",
    "192.168.1.6": "Gate In",
    "192.168.1.7": "R. Resepsionis",
    "192.168.1.8": "R. Meeting Lt.1",
    "192.168.1.9": "R. Lead Content",
    "192.168.1.10": "R. Content 4 Lt.2",
    "192.168.1.11": "Musholla",
    "192.168.1.12": "View Gudang & Toilet Lt.1",
    "192.168.1.13": "R. Infra",
    "192.168.1.14": "View FAT & CEO Lt.2",
    "192.168.1.15": "View Koridor Lt.2",
    "192.168.1.16": "Gate Out 2",
    "192.168.1.17": "R. SD 1 Lt.2",
    "192.168.1.18": "Pantry",
    "192.168.1.19": "Gate Out 1",
    "192.168.1.20": "Showroom 1",
    "192.168.1.21": "R. Project Lt.1",
    "192.168.1.22": "Showroom 2",
    "192.168.1.23": "R. Procurement",
    "192.168.1.24": "Break Room",
    "192.168.1.25": "Gudang Lt.2",
    "192.168.1.26": "R. Project Lt.2",
    "192.168.1.27": "R.BD",
    "192.168.1.28": "R. FM",
    "192.168.1.29": "Gate Middle",
    "192.168.1.30": "R. Content 1 Lt.2",
    "192.168.1.31": "R. SD 2 Lt.2",
    "192.168.1.33": "R. Content 3 Lt.2"
}

# ─── iTop Helpers ────────────────────────────────────────────
def itop_req(payload):
    r = requests.post(ITOP_URL, data={"auth_user": ITOP_USER, "auth_pwd": ITOP_PASS, "json_data": json.dumps(payload)})
    return r.json()

def get_or_create_brand(brand_name="Hikvision"):
    res = itop_req({"operation": "core/get", "class": "Brand", "key": f"SELECT Brand WHERE name='{brand_name}'", "output_fields": "id"})
    if res.get("objects"):
        return list(res["objects"].keys())[0].split("::")[1]
    # Create brand
    res = itop_req({"operation": "core/create", "class": "Brand", "output_fields": "id", "fields": {"name": brand_name}})
    return list(res["objects"].keys())[0].split("::")[1]

def get_or_create_model(model_name, brand_id):
    res = itop_req({"operation": "core/get", "class": "Model", "key": f"SELECT Model WHERE name='{model_name}'", "output_fields": "id"})
    if res.get("objects"):
        return list(res["objects"].keys())[0].split("::")[1]
    # Create model
    res = itop_req({
        "operation": "core/create", "class": "Model", "output_fields": "id",
        "fields": {"name": model_name, "brand_id": brand_id, "type": "NetworkDevice"},
        "comment": "Auto-created for CCTV sync"
    })
    return list(res["objects"].keys())[0].split("::")[1]

def get_org_id():
    res = itop_req({"operation": "core/get", "class": "Organization", "key": "SELECT Organization LIMIT 1", "output_fields": "id"})
    return list(res["objects"].keys())[0].split("::")[1] if res.get("objects") else "1"

# ─── ISAPI Helpers ───────────────────────────────────────────
def strip_namespace(tag):
    return tag.split('}', 1)[1] if '}' in tag else tag

def xml_to_dict(element):
    res = {}
    for child in element:
        tag = strip_namespace(child.tag)
        if len(child) > 0:
            val = xml_to_dict(child)
        else:
            val = child.text
        if tag in res:
            if not isinstance(res[tag], list):
                res[tag] = [res[tag]]
            res[tag].append(val)
        else:
            res[tag] = val
    return res

def fetch_nvr_channels():
    print(f"Connecting to NVR at {NVR_IP} to fetch CCTV data...")
    url = f"http://{NVR_IP}/ISAPI/ContentMgmt/InputProxy/channels"
    r = requests.get(url, auth=requests.auth.HTTPDigestAuth(NVR_USER, NVR_PASS), timeout=15)
    if not r.ok:
        print(f"Failed to fetch NVR ISAPI: HTTP {r.status_code}")
        return {}
    
    root = ET.fromstring(r.content)
    parsed = xml_to_dict(root)
    channels = parsed.get("InputProxyChannel", [])
    if isinstance(channels, dict):
        channels = [channels]
        
    mapping = {}
    for ch in channels:
        desc = ch.get("sourceInputPortDescriptor", {})
        ip = desc.get("ipAddress")
        sn = desc.get("serialNumber")
        model = desc.get("model") or "DS-2CD1121-I"
        if ip and sn:
            mapping[ip] = {"sn": sn, "model": model}
    
    print(f"Found {len(mapping)} active channels on NVR.")
    return mapping

# ─── Main Logic ──────────────────────────────────────────────
def sanitize_name(name):
    # Convert "R. Content 2 View2" -> "R-CONTENT-2-VIEW2"
    clean = re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').upper()
    return f"FALAH01-CCTV-{clean}"

def main():
    brand_id = get_or_create_brand("Hikvision")
    org_id = get_org_id()
    
    nvr_data = fetch_nvr_channels()
    
    models_cache = {}
    created_count = 0
    updated_count = 0
    
    for ip, loc_name in CCTV_TARGETS.items():
        ci_name = sanitize_name(loc_name)
        
        # Get data from NVR if available
        cam_info = nvr_data.get(ip, {})
        sn = cam_info.get("sn", f"CCTV-IP-{ip.replace('.', '-')}")
        model_name = cam_info.get("model", "DS-2CD1121-I")
        
        # Get or create model
        if model_name not in models_cache:
            models_cache[model_name] = get_or_create_model(model_name, brand_id)
        model_id = models_cache[model_name]
        
        # Check if CI exists
        chk = itop_req({"operation": "core/get", "class": "NetworkDevice", "key": f"SELECT NetworkDevice WHERE name='{ci_name}'", "output_fields": "id"})
        
        fields = {
            "name": ci_name,
            "org_id": org_id,
            "status": "production",
            "business_criticity": "medium",
            "managementip": ip,
            "serialnumber": sn,
            "asset_number": sn,
            "model_id": model_id,
            "networkdevicetype_id": "63",  # Generic
            "description": f"Location: {loc_name}"
        }
        
        if chk.get("objects"):
            # Update
            res = itop_req({
                "operation": "core/update",
                "class": "NetworkDevice",
                "key": f"SELECT NetworkDevice WHERE name='{ci_name}'",
                "fields": fields,
                "comment": "Sync CCTV data from NVR"
            })
            if res.get("code") == 0:
                print(f"✅ Updated: {ci_name} (IP: {ip}, SN: {sn})")
                updated_count += 1
            else:
                print(f"❌ Failed to update {ci_name}: {res}")
        else:
            # Create
            res = itop_req({
                "operation": "core/create",
                "class": "NetworkDevice",
                "fields": fields,
                "comment": "Sync CCTV data from NVR"
            })
            if res.get("code") == 0:
                print(f"✅ Created: {ci_name} (IP: {ip}, SN: {sn})")
                created_count += 1
            else:
                print(f"❌ Failed to create {ci_name}: {res}")
                
    print(f"\nCompleted! Created: {created_count}, Updated: {updated_count}")

if __name__ == "__main__":
    main()
