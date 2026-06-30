#!/usr/bin/env python3
import os
import requests
import json

ITOP_URL  = os.getenv("ITOP_URL",  "http://localhost:8080/webservices/rest.php?version=1.3")
ITOP_USER = os.getenv("ITOP_USER", "admin")
ITOP_PASS = os.getenv("ITOP_PASS", "Inovasi@0918")

def main():
    print("Mencari duplikat 'IP CAMERA' di iTop...")
    
    data = {
        "auth_user": ITOP_USER,
        "auth_pwd":  ITOP_PASS,
        "json_data": json.dumps({
            "operation": "core/get",
            "class": "NetworkDevice",
            "key": "SELECT NetworkDevice WHERE name = 'IP CAMERA'",
            "output_fields": "name,managementip"
        })
    }
    
    r = requests.post(ITOP_URL, data=data)
    r.raise_for_status()
    resp = r.json()
    
    objs = resp.get("objects", {})
    if not objs:
        print("Tidak ada duplikat 'IP CAMERA' yang ditemukan.")
        return
        
    print(f"Ditemukan {len(objs)} objek 'IP CAMERA'. Menghapus...")
    
    for key, val in objs.items():
        obj_id = key.split("::")[-1] if "::" in key else key
        ip = val.get("fields", {}).get("managementip", "N/A")
        
        del_data = {
            "auth_user": ITOP_USER,
            "auth_pwd":  ITOP_PASS,
            "json_data": json.dumps({
                "operation": "core/delete",
                "class": "NetworkDevice",
                "key": obj_id,
                "comment": "Menghapus duplikat generik IP CAMERA"
            })
        }
        del_r = requests.post(ITOP_URL, data=del_data)
        if del_r.json().get("code") == 0:
            print(f"  ✓ Berhasil menghapus ID {obj_id} (IP: {ip})")
        else:
            print(f"  ✗ Gagal menghapus ID {obj_id}: {del_r.text}")
            
    print("Pembersihan selesai! Consumer Kafka akan membuat ulang perangkat-perangkat ini dengan nama yang benar.")

if __name__ == "__main__":
    main()
