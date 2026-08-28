import sys
import os
sys.path.append("/home/infra/dcim_metrics_project")

from src.connectors.itsm.servicenow import ServiceNowConnector
from src.connectors.itsm.jira import JiraConnector
import json

def trigger_test_incident():
    # 1. Simulate an event coming from our new Virtualization Poller that exceeded an impact score threshold
    critical_event = {
        "event_type": "high_cpu_utilization",
        "hostname": "PROD-SRV-WEB",
        "severity": "critical",
        "impact_score": 25,
        "metrics": {
            "cpu_usage": 98.5
        }
    }

    print(f"Triggering ITSM Integration for Critical Event on {critical_event['hostname']}...")

    # 2. Trigger ServiceNow
    print("\n--- Sending to ServiceNow ---")
    sn_connector = ServiceNowConnector(instance_url="http://localhost:8083")
    sn_result = sn_connector.create_ticket(critical_event)
    
    if sn_result:
        print(f"ServiceNow returned Ticket Number: {sn_result.get('number')} with SysID: {sn_result.get('sys_id')}")

    # 3. Trigger Jira
    print("\n--- Sending to Jira ---")
    jira_connector = JiraConnector(instance_url="http://localhost:8083")
    jira_result = jira_connector.create_issue(critical_event)
    
    if jira_result:
        print(f"Jira returned Issue Key: {jira_result.get('key')} and ID: {jira_result.get('id')}")

if __name__ == "__main__":
    trigger_test_incident()
