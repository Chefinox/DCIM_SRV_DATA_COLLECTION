import requests
from requests.auth import HTTPDigestAuth
import urllib3
import logging

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class HikvisionClient:
    def __init__(self, host, user, password, timeout=5):
        self.host = host
        self.auth_digest = HTTPDigestAuth(user, password)
        self.auth_basic = (user, password)
        self.timeout = timeout

    def get_isapi(self, path):
        """Standard ISAPI GET request with auto fallback to Basic Auth."""
        url = f"http://{self.host}/ISAPI{path}"
        try:
            # Try Digest first
            response = requests.get(url, auth=self.auth_digest, timeout=self.timeout)
            if response.status_code == 200:
                return response.text
            
            # Fallback to Basic if Unauthorized
            if response.status_code == 401:
                response = requests.get(url, auth=self.auth_basic, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
            
            logging.warning(f"Hikvision ISAPI [{self.host}{path}] returned status: {response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Hikvision Communication Error [{self.host}]: {e}")
            return None
