#!/usr/bin/env python3
import json
import logging
import requests
import subprocess
import os

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("batch_sync")

ITOP_URL = 'http://localhost:8080/webservices/rest.php?version=1.3'
ITOP_USER = 'admin'
ITOP_PASS = 'Inovasi@0918'

DEVICES = [
    "FALAH01-FIT-CORE-RTR",
    "FALAH01-FIT-CORE-SW",
    "FALAH01-FIT-DIST-SW-LAN1",
    "FALAH01-FIT-DIST-SW-SERVER2",
    "FALAH01-FIT-ROUTER-MK-FORTUNE",
    "FALAH01-LINK-BALANCER",
    "FALAH01-MK-SW-FORTUNE",
    "FALAH01-MK-SW-R.BD",
    "FALAH01-MK-SW-R.LEAD-CD",
    "FALAH01-MK-SW-SD",
    "FALAH01-MK-SW-SEC",
    "FALAH01-ROUTER-CCR-IFORTE"
]

def itop_query(oql: str, output_fields="*"):
    payload = {
        "operation": "core/get",
        "class": "PhysicalInterface",
        "key": oql,
        "output_fields": output_fields,
    }
    r = requests.post(ITOP_URL, data={
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload)
    })
    return r.json()

def main():
    success = []
    failed = []
    skipped = []

    for dev in DEVICES:
        LOG.info("=" * 60)
        LOG.info(f"Memeriksa perangkat: {dev}")
        
        # 1. Cek apakah ada interfaces di iTop
        oql = f"SELECT PhysicalInterface WHERE connectableci_id = (SELECT NetworkDevice WHERE name = '{dev}')"
        res = itop_query(oql)
        objects = res.get("objects", {})
        
        if objects:
            LOG.info(f"  -> Ditemukan {len(objects)} interfaces untuk {dev}. Melakukan BACKUP (di data dulu)...")
            backup_file = f"backup_interfaces_{dev}.json"
            with open(backup_file, "w") as f:
                json.dump(objects, f, indent=2)
            LOG.info(f"  -> Data disimpan di {backup_file}.")
            LOG.info(f"  -> SKIPPING (Lanjutkan hanya jika tidak ada interfaces).")
            skipped.append(dev)
            continue
            
        # 2. Jika tidak ada interface sama sekali, Lanjutkan!
        LOG.info(f"  -> Tidak ada interface di iTop. MELANJUTKAN SINKRONISASI...")
        
        # Panggil script sync_network_devices_itop.py
        cmd = ["python3", "/home/infra/dcim_metrics_project/itop/sync_network_devices_itop.py", "--device", dev]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            LOG.info(f"  -> SINKRONISASI BERHASIL untuk {dev}.")
            success.append(dev)
        else:
            LOG.error(f"  -> SINKRONISASI GAGAL untuk {dev}.")
            LOG.error(f"     Output error: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'Unknown error'}")
            failed.append({
                "device": dev,
                "error": result.stderr.strip()
            })

    # Summary
    LOG.info("=" * 60)
    LOG.info("SUMMARY REPORT")
    LOG.info("=" * 60)
    LOG.info(f"Berhasil: {len(success)}")
    for d in success:
        LOG.info(f"  - {d}")
        
    LOG.info(f"Skipped (Di Data Dulu karena ada interface): {len(skipped)}")
    for d in skipped:
        LOG.info(f"  - {d}")
        
    LOG.info(f"Gagal (Kredensial/Koneksi): {len(failed)}")
    for d in failed:
        LOG.info(f"  - {d['device']} -> Error bisa dilihat di log")
        
    with open("batch_sync_report.json", "w") as f:
        json.dump({
            "success": success,
            "skipped": skipped,
            "failed": failed
        }, f, indent=2)

if __name__ == "__main__":
    main()
