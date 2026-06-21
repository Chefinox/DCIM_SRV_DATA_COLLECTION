from src.tools.protocols.hikvision_client import HikvisionClient
import json

client = HikvisionClient("192.168.1.13", "admin", "F!tech0918")
info = client.get_isapi("/System/deviceInfo")
print("DeviceInfo ISAPI:")
print(info)
