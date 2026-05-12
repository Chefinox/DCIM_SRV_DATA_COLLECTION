import requests
from requests.auth import HTTPDigestAuth
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)

NVR_IP = "192.168.1.254"
NVR_USER = "admin"
NVR_PASS = "qRvbi883=Zk[Q)@5"

def test_nvr():
    url = f"http://{NVR_IP}/ISAPI/System/deviceInfo"
    print(f"Testing {url} with Digest Auth...")
    try:
        # 1. Try Digest
        resp = requests.get(url, auth=HTTPDigestAuth(NVR_USER, NVR_PASS), timeout=10)
        print(f"Digest Status: {resp.status_code}")
        if resp.status_code == 200:
            print("SUCCESS with Digest")
            return
            
        # 2. Try Basic
        print(f"Testing {url} with Basic Auth...")
        resp = requests.get(url, auth=(NVR_USER, NVR_PASS), timeout=10)
        print(f"Basic Status: {resp.status_code}")
        if resp.status_code == 200:
            print("SUCCESS with Basic")
            return

        # 3. Try with trailing slash or alternate paths
        for path in ["/ISAPI/System/status", "/ISAPI/Streaming/channels"]:
            url_alt = f"http://{NVR_IP}{path}"
            print(f"Testing {url_alt}...")
            resp = requests.get(url_alt, auth=HTTPDigestAuth(NVR_USER, NVR_PASS), timeout=10)
            print(f"Path {path} Status: {resp.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_nvr()
