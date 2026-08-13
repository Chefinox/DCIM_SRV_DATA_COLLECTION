import requests
import json
from datetime import datetime

class ServiceNowConnector:
    def __init__(self, instance_url="http://localhost:8083", username="admin", password="password"):
        self.instance_url = instance_url
        self.auth = (username, password)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

    def transform_to_dcim(self, incident_data):
        # Maps ServiceNow ticket data back to DCIM
        return {
            "source": "servicenow",
            "ticket_number": incident_data.get("number"),
            "status": incident_data.get("state"),
            "sys_id": incident_data.get("sys_id")
        }

    def create_ticket(self, event_data):
        # Maps DCIM alert to ServiceNow incident
        url = f"{self.instance_url}/api/now/table/incident"
        payload = {
            "short_description": f"DCIM Alert: {event_data.get('event_type')} on {event_data.get('hostname')}",
            "description": json.dumps(event_data, indent=2),
            "urgency": "1" if event_data.get("severity") == "critical" else "2",
            "caller_id": "DCIM_System"
        }
        
        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, json=payload)
            if response.status_code == 201:
                result = response.json().get('result', {})
                print(f"Successfully created ServiceNow ticket: {result.get('number')}")
                return result
            else:
                print(f"Failed to create ServiceNow ticket: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error communicating with ServiceNow Mock API: {e}")
            return None
