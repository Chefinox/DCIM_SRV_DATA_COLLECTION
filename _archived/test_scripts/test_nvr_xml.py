from src.schemas.transformers.cctv_metadata import parse_isapi_xml, transform_to_cctv_metrics

xml = """<?xml version="1.0" encoding="UTF-8" ?>
<hddList version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<hdd version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>1</id>
<status>ok</status>
<capacity>3815447</capacity>
<freeSpace>0</freeSpace>
</hdd>
<hdd version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
<id>2</id>
<status>ok</status>
<capacity>3815447</capacity>
<freeSpace>0</freeSpace>
</hdd>
</hddList>"""

parsed = parse_isapi_xml(xml)
print("Parsed:", parsed)
res = transform_to_cctv_metrics("192.168.1.254", {"model":"DS-NVR"}, None, parsed)
print("Storage metrics:", res.get("storage"))
