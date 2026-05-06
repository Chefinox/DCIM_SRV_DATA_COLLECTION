import requests
import urllib3
import logging

# Disable SSL warnings for BMCs with self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RedfishClient:
    def __init__(self, host, user, password, timeout=10):
        self.base_url = f"https://{host}/redfish/v1"
        self.auth = (user, password)
        self.timeout = timeout

    def get(self, endpoint):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(
                url, 
                auth=self.auth, 
                verify=False, 
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Redfish GET Error [{url}]: {e}")
            return None

    def get_system_summary(self):
        """Helper to get common system info in one call (simplification)"""
        systems = self.get("Systems/1")
        chassis = self.get("Chassis/Self")
        return {"systems": systems, "chassis": chassis}
