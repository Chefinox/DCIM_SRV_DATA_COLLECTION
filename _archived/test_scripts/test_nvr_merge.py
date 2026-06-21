from src.tools.protocols.hikvision_client import HikvisionClient
from src.schemas.transformers.cctv_metadata import parse_isapi_xml
import json

client = HikvisionClient("192.168.1.254", "admin", "qRvbi883=Zk[Q)@5")
xml_data = client.get_isapi("/ContentMgmt/InputProxy/channels")
channels = parse_isapi_xml(xml_data).get("InputProxyChannel", [])
if isinstance(channels, dict): channels = [channels]
mapping = {}
for ch in channels:
    desc = ch.get("sourceInputPortDescriptor", {})
    ip = desc.get("ipAddress")
    if ip:
        mapping[ip] = {"id": ch.get("id")}

status_xml = client.get_isapi("/ContentMgmt/InputProxy/channels/status")
statuses = parse_isapi_xml(status_xml).get("InputProxyChannelStatus", [])
if isinstance(statuses, dict): statuses = [statuses]
for st in statuses:
    desc = st.get("sourceInputPortDescriptor", {})
    ip = desc.get("ipAddress")
    online = st.get("online")
    if ip and ip in mapping:
        mapping[ip]["online"] = (str(online).lower() == "true")

print(json.dumps(mapping, indent=2))
