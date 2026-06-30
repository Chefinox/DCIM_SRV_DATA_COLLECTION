#!/usr/bin/env python3
"""
cleanup_duplicate_ci.py
Membersihkan CI duplikat di iTop berdasarkan nama hostname.
Menyisakan CI dengan ID terkecil (yang paling lama dibuat).
"""
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

ITOP_URL = 'http://localhost:8080/webservices/rest.php?version=1.3'
ITOP_USER = 'admin'
ITOP_PASS = 'Inovasi@0918'

CLASSES_TO_CHECK = ["Server", "NetworkDevice", "StorageSystem", "PowerConnection"]

def itop_post(payload):
    r = requests.post(ITOP_URL, data={
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload)
    }, timeout=15)
    r.raise_for_status()
    return r.json()

def get_all_ci(class_name):
    """Ambil semua CI dari kelas tertentu."""
    body = itop_post({
        "operation": "core/get",
        "class": class_name,
        "key": f"SELECT {class_name}",
        "output_fields": "name,serialnumber,description"
    })
    objects = body.get("objects") or {}
    result = []
    for key, obj in objects.items():
        obj_id = int(key.split("::")[-1])
        name = obj["fields"].get("name", "")
        description = obj["fields"].get("description", "")
        result.append({"id": obj_id, "name": name, "description": description})
    return result

def delete_ci(class_name, obj_id):
    """Hapus CI berdasarkan ID."""
    body = itop_post({
        "operation": "core/delete",
        "class": class_name,
        "key": str(obj_id),
        "comment": "Auto-deleted: duplicate CI by cleanup_duplicate_ci.py"
    })
    return body.get("code") == 0

def main():
    total_deleted = 0
    
    for cls in CLASSES_TO_CHECK:
        logger.info(f"Checking class: {cls}")
        try:
            items = get_all_ci(cls)
        except Exception as e:
            logger.error(f"Failed to get {cls}: {e}")
            continue
        
        # Group by name (hostname)
        by_name = {}
        for item in items:
            name = item["name"].strip()
            if not name:
                continue
            by_name.setdefault(name, []).append(item)
        
        # Find duplicates
        for name, entries in by_name.items():
            if len(entries) <= 1:
                continue
            
            # Sort by ID ascending → keep the first (oldest/smallest ID)
            entries.sort(key=lambda x: x["id"])
            keep = entries[0]
            duplicates = entries[1:]
            
            logger.warning(
                f"[{cls}] Duplikat ditemukan untuk '{name}': "
                f"Keep ID={keep['id']}, Delete IDs={[d['id'] for d in duplicates]}"
            )
            
            for dup in duplicates:
                try:
                    success = delete_ci(cls, dup["id"])
                    if success:
                        logger.info(f"  ✓ Deleted {cls} ID={dup['id']} (name='{name}')")
                        total_deleted += 1
                    else:
                        logger.error(f"  ✗ Failed to delete {cls} ID={dup['id']}")
                except Exception as e:
                    logger.error(f"  ✗ Error deleting {cls} ID={dup['id']}: {e}")
    
    logger.info(f"\n=== Cleanup selesai. Total dihapus: {total_deleted} CI duplikat ===")

if __name__ == "__main__":
    main()
