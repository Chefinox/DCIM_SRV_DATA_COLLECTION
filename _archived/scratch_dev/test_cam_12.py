import requests
from requests.auth import HTTPDigestAuth
import urllib3

urllib3.disable_warnings()

IP = "192.168.1.12"
PASSWORDS = ["F!tech0918", "F!tech@0918", "12345", "admin123", "Falah0918", "Inovasi@0918"]

print(f"Testing ISAPI connection to {IP}...")
for pwd in PASSWORDS:
    try:
        url = f"http://{IP}/ISAPI/System/deviceInfo"
        r = requests.get(url, auth=HTTPDigestAuth("admin", pwd), timeout=5, verify=False)
        print(f"Password '{pwd}': HTTP {r.status_code}")
        if r.status_code == 200:
            print("SUCCESS!")
            print(r.text)
            break
    except Exception as e:
        print(f"Password '{pwd}': Error - {e}")
