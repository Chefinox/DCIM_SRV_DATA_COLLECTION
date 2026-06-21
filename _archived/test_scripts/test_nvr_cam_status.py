from src.tools.protocols.hikvision_client import HikvisionClient
client = HikvisionClient("192.168.1.254", "admin", "qRvbi883=Zk[Q)@5")
print(client.get_isapi("/ContentMgmt/InputProxy/channels/status"))
