from src.skills.security.cctv_poller.executor import CCTVPollerExecutor
import json

executor = CCTVPollerExecutor()
mapping = executor.discover_nvr_channels("192.168.1.254", "admin", "qRvbi883=Zk[Q)@5")
print("NVR Proxy Mapping for 192.168.1.13:")
print(json.dumps(mapping.get("192.168.1.13"), indent=2))
