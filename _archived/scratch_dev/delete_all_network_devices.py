#!/usr/bin/env python3
"""
Hapus semua NetworkDevice dari iTop secara batch.
"""
import json
import requests
import time

ITOP_URL  = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER = "admin"
ITOP_PASS = "Inovasi@0918"

def itop_post(payload, timeout=30):
    data = {
        "auth_user": ITOP_USER,
        "auth_pwd":  ITOP_PASS,
        "json_data": json.dumps(payload)
    }
    r = requests.post(ITOP_URL, data=data, timeout=timeout)
    return r.json()

def get_all_ids(page=1, limit=200):
    res = itop_post({
        "operation": "core/get",
        "class": "NetworkDevice",
        "key": "SELECT NetworkDevice",
        "output_fields": "name",
        "limit": limit,
        "page": page
    })
    objs = res.get("objects") or {}
    return {k.split("::")[-1]: v["fields"]["name"] for k, v in objs.items()}

def delete_device(obj_id, name):
    res = itop_post({
        "operation": "core/delete",
        "class": "NetworkDevice",
        "key": obj_id,
        "comment": "Bulk delete - reset untuk rebuild dari Kafka",
        "simulate": False
    })
    return res.get("code") == 0

print("=== Mulai hapus semua NetworkDevice ===")

page = 1
total_deleted = 0
total_failed  = 0

while True:
    print(f"\n[Page {page}] Mengambil batch NetworkDevice...")
    ids = get_all_ids(page=1, limit=200)  # selalu page=1 karena setelah delete urutan berubah
    
    if not ids:
        print("Tidak ada lagi NetworkDevice. Selesai!")
        break
    
    print(f"  Ditemukan {len(ids)} device, mulai hapus...")
    
    batch_deleted = 0
    batch_failed  = 0
    
    for obj_id, name in ids.items():
        ok = delete_device(obj_id, name)
        if ok:
            batch_deleted += 1
            print(f"  ✓ Deleted: {name} (ID={obj_id})")
        else:
            batch_failed += 1
            print(f"  ✗ Failed:  {name} (ID={obj_id})")
        time.sleep(0.05)  # throttle agar tidak overload iTop
    
    total_deleted += batch_deleted
    total_failed  += batch_failed
    print(f"  Batch selesai: {batch_deleted} berhasil, {batch_failed} gagal")
    
    if batch_deleted == 0 and batch_failed == len(ids):
        print("Semua item gagal dihapus, berhenti.")
        break

print(f"\n=== SELESAI: {total_deleted} deleted, {total_failed} failed ===")
