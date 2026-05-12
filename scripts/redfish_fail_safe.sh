#!/bin/bash
LOG_FILE="/home/infra/dcim_metrics_project/logs/redfish_test.log"
CONF_FILE="/etc/telegraf/telegraf.d/servers-redfish.conf"

tail -f /var/log/syslog | grep --line-buffered "telegraf" | grep --line-buffered "redfish" | while read line; do
    if echo "$line" | grep -qiE "error|timeout|refused"; then
        echo "[$(date)] CRITICAL: Redfish Error Detected: $line" >> $LOG_FILE
        # Jika error terdeteksi, turunkan ke 60s sebagai pengaman
        sudo sed -i 's/interval = "30s"/interval = "60s"/g' $CONF_FILE
        sudo systemctl restart telegraf
        echo "[$(date)] ALERT: High load detected. Auto-reverted to 60s for safety." >> $LOG_FILE
        exit 0 # Berhenti setelah revert
    fi
done
