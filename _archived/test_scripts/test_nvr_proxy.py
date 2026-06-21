from src.schemas.transformers.cctv_metadata import parse_isapi_xml
from src.tools.protocols.hikvision_client import HikvisionClient

client = HikvisionClient("192.168.1.254", "admin", "qRvbi883=Zk[Q)@5")
xml_data = client.get_isapi("/ContentMgmt/InputProxy/channels")
parsed = parse_isapi_xml(xml_data)

print("Keys in parsed:", parsed.keys())
channels = parsed.get("InputProxyChannel", [])
print("Number of channels:", len(channels))
if channels:
    print("First channel descriptor:", channels[0].get("sourceInputPortDescriptor"))
