import json
import logging
from dcim_itop_unified_consumer import ITopClient, process_message

logging.basicConfig(level=logging.DEBUG)

msg_val = '''{"event_id": "2608c214-4d38-4252-9fcd-2f6c6059f14c", "event_time": "2026-06-05T02:14:30+00:00", "timestamp": 1780625670, "source_topic": "dcim.raw.network.interfaces", "measurement": "interface", "device_type": "network_switch", "hostname": "FIT-Core-RTR", "ip": "172.16.35.1", "serial_number": "HC707RR1T60", "metric_name": "interface_status", "metric_value": 2, "metric_unit": "status_code", "severity": "info", "manufacturer": null, "model": "RouterOS CCR2004-16G-2S+", "firmware": "7.16.2", "raw_fields": {"ifAdminStatus": 1, "ifDescr": "ether12", "ifInDiscards": 0, "ifInErrors": 0, "ifInNUcastPkts": 0, "ifInOctets": 0, "ifInUcastPkts": 0, "ifInUnknownProtos": 0, "ifLastChange": 1179, "ifMtu": 1500, "ifOperStatus": 2, "ifOutDiscards": 0, "ifOutErrors": 0, "ifOutNUcastPkts": 0, "ifOutOctets": 0, "ifOutQLen": 0, "ifOutUcastPkts": 0, "ifPhysAddress": "dc:2c:6e:c7:c9:57", "ifSpecific": ".0.0", "ifSpeed": 1000000000, "ifType": 6, "if_in_octets": 0, "if_name": "ether12", "if_oper_status": 2, "if_out_octets": 0}, "raw_tags": {"firmware": "7.16.2", "hostname": "FIT-Core-RTR", "ifIndex": "12", "ip": "172.16.35.1", "model": "RouterOS CCR2004-16G-2S+", "serial_number": "HC707RR1T60"}}'''

client = ITopClient()
process_message(msg_val, client, "1")
