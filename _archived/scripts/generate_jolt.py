import re
import json

conf_path = '/home/infra/dcim_metrics_project/configs/telegraf/ups-apc.conf'
with open(conf_path, 'r') as f:
    content = f.read()

fields = re.findall(r'name\s*=\s*"([^"]+)"\s*oid\s*=\s*"\.?([^"]+)"', content)

shift_spec = {}
for name, oid in fields:
    # Jolt requires escaping dots in keys
    escaped_oid = oid.replace('.', '\\\\.')
    key = f"snmp${escaped_oid}$*"
    shift_spec[key] = f"payload.{name}"

# Telegraf structure usually expects:
# {
#   "measurement": "ups_apc",
#   "tags": {
#     "device_type": "ups",
#     "location": "Server Room"
#   },
#   "fields": {
#      ...
#   }
# }
# But wait, looking at metric_mapping.json for how it normalizes, 
# Telegraf JSON outputs fields flat or under fields? 
# Usually Telegraf MQTT/Kafka JSON format is:
# {
#   "fields": {
#     "battery_status": 2,
#     ...
#   },
#   "name": "ups_apc",
#   "tags": {
#     "device_type": "ups",
#     "host": "..."
#   },
#   "timestamp": 123456789
# }

# Let's check what metric_mapping.json expects, oh I couldn't find it. 
# Let's just output the Jolt spec to a file and I will read it.

jolt = [
  {
    "operation": "shift",
    "spec": shift_spec
  },
  {
    "operation": "default",
    "spec": {
      "name": "ups_apc",
      "tags": {
        "device_type": "ups",
        "location": "Server Room"
      },
      "timestamp": "${now():toNumber()}" # We will let NiFi expression language handle this outside Jolt, or just leave it empty.
    }
  }
]

print(json.dumps(jolt, indent=2))
