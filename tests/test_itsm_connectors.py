import unittest
from src.connectors.itsm.servicenow import ServiceNowConnector
from src.connectors.itsm.jira import JiraConnector

class TestITSMConnectors(unittest.TestCase):
    def test_servicenow_create(self):
        # Requires the mock API to be running on 8083
        connector = ServiceNowConnector()
        test_event = {"event_type": "high_temp", "hostname": "TEST-SERVER", "severity": "critical"}
        result = connector.create_ticket(test_event)
        
        self.assertIsNotNone(result)
        self.assertIn("INC", result.get("number"))
        self.assertEqual(result.get("state"), "New")
        
    def test_jira_create(self):
        # Requires the mock API to be running on 8083
        connector = JiraConnector()
        test_event = {"event_type": "high_temp", "hostname": "TEST-SERVER", "severity": "critical"}
        result = connector.create_issue(test_event)
        
        self.assertIsNotNone(result)
        self.assertIn("DCIM-", result.get("key"))

if __name__ == '__main__':
    unittest.main()
