#!/bin/bash
# setup_secrets.sh — Recreate Docker secrets di /run/secrets/dcim/ setelah reboot
# Secrets ini dibutuhkan oleh: dcim-redis-cache, dcim-nifi, dcim-redis-sync, dcim-sql-consumer
#
# JALANKAN: sudo bash /home/infra/dcim_metrics_project/scripts/setup_secrets.sh
# KAPAN: Setelah server reboot (karena /run adalah tmpfs dan hilang saat reboot)
#
# MIGRATION NOTE (2026-06-01):
#   Database SOT sudah dipindah ke container dcim_sot_postgres di server ini (10.70.0.56)
#   Ralph CMDB sudah dipindah ke container ralph_nginx port 8082 di server ini
#   Host lama (192.168.100.115 dan 192.168.101.73) sudah tidak aktif

set -e

echo "[setup_secrets] Creating /run/secrets/dcim/ ..."
mkdir -p /run/secrets/dcim

# Database SOT PostgreSQL (container dcim_sot_postgres, localhost:5432)
echo -n "localhost"            > /run/secrets/dcim/sot_db_host
echo -n "dcim_sot"            > /run/secrets/dcim/sot_db_name
echo -n "sot_admin"           > /run/secrets/dcim/sot_db_user
echo -n "Inovasi@0918"        > /run/secrets/dcim/sot_db_pass

# Ralph CMDB API (container ralph_nginx, localhost:8082)
echo -n "1cd05b8d36e258399a52c59f1a4016addb2346a3" > /run/secrets/dcim/ralph_api_token

# Device credentials
echo -n "F!tech@0918"         > /run/secrets/dcim/redfish_pass
echo -n "qRvbi883=Zk[Q)@5"   > /run/secrets/dcim/hikvision_nvr_pass
echo -n "F!tech0918"          > /run/secrets/dcim/hikvision_cam_pass
echo -n "F!tech0918"          > /run/secrets/dcim/nas_pass_rest
echo -n "F!tech0918"          > /run/secrets/dcim/nas_pass_snmp
echo -n "F!tech0918"          > /run/secrets/dcim/ups_snmp_auth_pass
echo -n "F!tech0918"          > /run/secrets/dcim/ups_snmp_priv_pass
echo -n "nifi_admin"          > /run/secrets/dcim/nifi_password

# Set permissions (readable by all, no execute)
chmod 644 /run/secrets/dcim/*

echo "[setup_secrets] Done. Secrets created:"
ls -la /run/secrets/dcim/

echo ""
echo "[setup_secrets] Restarting affected Docker containers..."
docker start dcim-redis-cache 2>/dev/null && echo "  dcim-redis-cache: started" || echo "  dcim-redis-cache: already running or failed"
docker start dcim-nifi        2>/dev/null && echo "  dcim-nifi: started"        || echo "  dcim-nifi: already running or failed"
docker start dcim-kafka-ui    2>/dev/null && echo "  dcim-kafka-ui: started"    || echo "  dcim-kafka-ui: already running or failed"

echo ""
echo "[setup_secrets] Restarting affected systemd services..."
systemctl restart dcim-redis-sync   && echo "  dcim-redis-sync: restarted"   || echo "  dcim-redis-sync: failed"
systemctl restart dcim-sql-consumer && echo "  dcim-sql-consumer: restarted" || echo "  dcim-sql-consumer: failed"

echo ""
echo "[setup_secrets] DONE. System ready."
