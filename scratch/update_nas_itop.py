#!/usr/bin/env python3
"""
Update iTop NAS CIs with real data from devices (SNMP confirmed + user-verified).
Skips NAS-01 (Central NAS - RS2423RP, no SNMP response in range)
Skips NAS-06 (NAS SD / NAS-SD01 - unreachable)

Mapping from iTop description field:
  NAS::68 FALAH01-NAS-01  Central NAS   -> SKIP (device not reachable)
  NAS::69 FALAH01-NAS-02  NAS CD 01     -> NAS-CD01 (10.50.0.109) DS920+ SN:21B0TERQ1SS9A
  NAS::70 FALAH01-NAS-03  NAS CD 02     -> NAS-CD02 (10.50.0.110) DS920+ SN:2270SBRXKZY8V
  NAS::71 FALAH01-NAS-04  NAS FAT       -> NAS-FAT  (10.50.0.107) DS220+ SN:2230RLRHB9A4J
  NAS::72 FALAH01-NAS-05  NAS INFRA     -> NAS-INFRA(10.50.0.106) DS220+ SN:2240RLRRFW9D4
  NAS::73 FALAH01-NAS-06  NAS SD        -> SKIP (NAS-SD01 unreachable)
"""

import requests
import json

ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER = "admin"
ITOP_PASS = "Inovasi@0918"

# Data confirmed: SNMP from device + user-verified serial numbers
updates = [
    {
        "itop_name": "FALAH01-NAS-02",
        "itop_key": "NAS::69",
        "hostname": "NAS-CD01",
        "fields": {
            "managementip": "10.50.0.109",
            "serialnumber":  "21B0TERQ1SS9A",   # User-verified via DSM web
            "asset_number":  "21B0TERQ1SS9A",
            # Model DS920+ must be looked up by name in iTop
        },
        "model_name": "DS920+",
    },
    {
        "itop_name": "FALAH01-NAS-03",
        "itop_key": "NAS::70",
        "hostname": "NAS-CD02",
        "fields": {
            "managementip": "10.50.0.110",
            "serialnumber":  "2270SBRXKZY8V",   # User-verified via DSM web
            "asset_number":  "2270SBRXKZY8V",
        },
        "model_name": "DS920+",
    },
    {
        "itop_name": "FALAH01-NAS-04",
        "itop_key": "NAS::71",
        "hostname": "NAS-FAT",
        "fields": {
            "managementip": "10.50.0.107",
            "serialnumber":  "2230RLRHB9A4J",   # From SNMP OID 6574.1.5.2.0
            "asset_number":  "2230RLRHB9A4J",
        },
        "model_name": "DS220+",
    },
    {
        "itop_name": "FALAH01-NAS-05",
        "itop_key": "NAS::72",
        "hostname": "NAS-INFRA",
        "fields": {
            "managementip": "10.50.0.106",
            "serialnumber":  "2240RLRRFW9D4",   # From SNMP authNoPriv (device uses lower security)
            "asset_number":  "2240RLRRFW9D4",
        },
        "model_name": "DS220+",
    },
]

skipped = [
    {"itop_name": "FALAH01-NAS-01", "reason": "Central NAS (RS2423RP) - device not reachable via SNMP, no confirmed data"},
    {"itop_name": "FALAH01-NAS-06", "reason": "NAS SD (NAS-SD01) - unreachable at 10.50.0.108"},
]


def itop_post(payload: dict) -> dict:
    resp = requests.post(
        ITOP_URL,
        data={
            "auth_user": ITOP_USER,
            "auth_pwd":  ITOP_PASS,
            "json_data": json.dumps(payload),
        },
        timeout=30,
    )
    return resp.json()


def get_model_id(model_name: str) -> str | None:
    """Look up Model ID in iTop by name."""
    payload = {
        "operation":    "core/get",
        "class":        "Model",
        "key":          f"SELECT Model WHERE name='{model_name}'",
        "output_fields": "id, name",
    }
    result = itop_post(payload)
    objects = result.get("objects") or {}
    if objects:
        key = list(objects.keys())[0]
        return objects[key]["fields"]["id"]
    return None


def update_nas(entry: dict):
    name = entry["itop_name"]
    hostname = entry["hostname"]
    fields = entry["fields"].copy()
    model_name = entry.get("model_name")

    print(f"\n{'='*60}")
    print(f"Updating: {name} ({hostname})")
    print(f"  Fields: {fields}")

    # Resolve model_id if model_name given
    if model_name:
        model_id = get_model_id(model_name)
        if model_id:
            fields["model_id"] = model_id
            print(f"  Model '{model_name}' resolved to id={model_id}")
        else:
            print(f"  WARNING: Model '{model_name}' not found in iTop — skipping model update")

    payload = {
        "operation":    "core/update",
        "class":        "NAS",
        "key":          f"SELECT NAS WHERE name='{name}'",
        "output_fields": "name, serialnumber, managementip",
        "fields":       fields,
        "comment":      f"SNMP/user-verified update for {hostname} via AI agent",
    }
    result = itop_post(payload)
    code = result.get("code")
    if code == 0:
        obj = list(result["objects"].values())[0]
        print(f"  ✅ SUCCESS: {obj['message']} — SN={obj['fields'].get('serialnumber')}, IP={obj['fields'].get('managementip')}")
    else:
        print(f"  ❌ FAILED: code={code}, message={result.get('message')}")


# ── Main ───────────────────────────────────────────────────────────────────────
print("=== iTop NAS Update — SNMP + User-Verified Data ===\n")

print("Skipped NAS CIs:")
for s in skipped:
    print(f"  ⏭️  {s['itop_name']}: {s['reason']}")

for entry in updates:
    update_nas(entry)

print("\n=== Done ===")
