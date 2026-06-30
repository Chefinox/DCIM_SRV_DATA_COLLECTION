#!/bin/bash
# CCTV Polling Diagnostic Script

echo "========================================="
echo "CCTV Polling Diagnostic Report"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="
echo ""

echo "1. Telegraf Service Status:"
systemctl is-active telegraf
echo ""

echo "2. Recent CCTV data in PostgreSQL (last 10 min):"
PGPASSWORD="Inovasi@0918" psql -h 192.168.101.73 -U sot_admin -d dcim_sot -t -c \
  "SELECT COUNT(*) as events, COUNT(DISTINCT serial_number) as cameras FROM dcim_events WHERE device_type = 'cctv' AND event_time > NOW() - INTERVAL '10 minutes';" 2>/dev/null || echo "PostgreSQL query failed"
echo ""

echo "3. Unique CCTV serial numbers (last 1 hour):"
PGPASSWORD="Inovasi@0918" psql -h 192.168.101.73 -U sot_admin -d dcim_sot -t -c \
  "SELECT COUNT(DISTINCT serial_number) FROM dcim_events WHERE device_type = 'cctv' AND event_time > NOW() - INTERVAL '1 hour';" 2>/dev/null || echo "PostgreSQL query failed"
echo ""

echo "4. Sample CCTV hostnames (last 1 hour):"
PGPASSWORD="Inovasi@0918" psql -h 192.168.101.73 -U sot_admin -d dcim_sot -t -c \
  "SELECT DISTINCT hostname, COUNT(*) as events FROM dcim_events WHERE device_type = 'cctv' AND event_time > NOW() - INTERVAL '1 hour' GROUP BY hostname ORDER BY events DESC LIMIT 10;" 2>/dev/null || echo "PostgreSQL query failed"
echo ""

echo "5. Kafka ISAPI topic check:"
timeout 5 docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic dcim.raw.device.isapi \
  --from-beginning \
  --max-messages 3 2>/dev/null | grep -o '"serial_number":"[^"]*"' | head -5 || echo "Kafka check failed"
echo ""

echo "6. Test manual CCTV polling (first 3 cameras):"
cd /home/infra/dcim_metrics_project
timeout 15 python3 -c "
import sys
sys.path.append('/home/infra/dcim_metrics_project')
from src.skills.security.cctv_poller.executor import CCTVPollerExecutor

executor = CCTVPollerExecutor()
test_ips = ['192.168.1.2', '192.168.1.3', '192.168.1.4']

for ip in test_ips:
    try:
        result = executor.poll_device(ip, 'admin', 'F!tech0918', 'CCTV')
        print(f'{ip}: SN={result.get(\"serial_number\", \"N/A\")}, Status={result.get(\"status\", \"N/A\")}')
    except Exception as e:
        print(f'{ip}: ERROR - {str(e)[:50]}')
" 2>&1 || echo "Manual polling test failed"
echo ""

echo "========================================="
echo "Diagnostic Complete"
echo "========================================="
