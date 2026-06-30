import json
import logging
from dcim_itop_unified_consumer import ITopClient, process_message

logging.basicConfig(level=logging.DEBUG)

msg_val = '''{
  "event_id": "24259d1b-56cc-4892-9ae7-1e4398d5c234",
  "event_time": "2026-06-05T02:14:30+00:00",
  "timestamp": 1780625670,
  "source_topic": "dcim.raw.network.snmp",
  "measurement": "mikrotik",
  "device_type": "network_switch",
  "hostname": "FIT-Core-RTR",
  "ip": "172.16.35.1",
  "serial_number": "HC707RR1T60",
  "metric_name": "general_metric",
  "metric_value": null,
  "metric_unit": null,
  "severity": "info",
  "manufacturer": null,
  "model": "RouterOS CCR2004-16G-2S+",
  "firmware": "7.16.2",
  "raw_fields": {"cpu_load": 17, "memory_used_kb": 834028},
  "raw_tags": {"firmware": "7.16.2", "hostname": "FIT-Core-RTR", "ip": "172.16.35.1", "model": "RouterOS CCR2004-16G-2S+", "serial_number": "HC707RR1T60"}
}'''

client = ITopClient()
process_message(msg_val, client, "1")
