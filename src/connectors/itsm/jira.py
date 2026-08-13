import requests
import json

class JiraConnector:
    def __init__(self, instance_url="http://localhost:8083", api_key="dummy_key", project_key="DCIM"):
        self.instance_url = instance_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.project_key = project_key

    def create_issue(self, event_data):
        url = f"{self.instance_url}/rest/api/2/issue"
        payload = {
            "fields": {
                "project": {
                    "key": self.project_key
                },
                "summary": f"DCIM Incident: {event_data.get('event_type')} on {event_data.get('hostname')}",
                "description": json.dumps(event_data, indent=2),
                "issuetype": {
                    "name": "Task"
                }
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            if response.status_code == 201:
                result = response.json()
                print(f"Successfully created Jira issue: {result.get('key')}")
                return result
            else:
                print(f"Failed to create Jira issue: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error communicating with Jira Mock API: {e}")
            return None
