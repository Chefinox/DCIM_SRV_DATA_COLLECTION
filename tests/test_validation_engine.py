import unittest
import time
from datetime import datetime, timedelta, timezone
from src.validation.engine import ValidationEngine

class TestValidationEngine(unittest.TestCase):
    def setUp(self):
        # We can bypass file load by overriding config
        self.engine = ValidationEngine("nonexistent.yaml")
        # Add basic rules manually for testing
        from src.validation.rules import RangeRule, FreshnessRule, SourceAllowlistRule
        self.engine.rules.append(RangeRule({'temperature': {'min': 0, 'max': 100}}))
        self.engine.rules.append(FreshnessRule(300))
        self.engine.rules.append(SourceAllowlistRule(['allowed-host']))

    def test_valid_event(self):
        event = {
            'hostname': 'allowed-host-1',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': {'temperature': 45.0}
        }
        self.assertTrue(self.engine.validate(event))

    def test_invalid_range(self):
        event = {
            'hostname': 'allowed-host-1',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': {'temperature': 150.0}
        }
        self.assertFalse(self.engine.validate(event))

    def test_invalid_freshness(self):
        old_time = datetime.now(timezone.utc) - timedelta(seconds=400)
        event = {
            'hostname': 'allowed-host-1',
            'timestamp': old_time.isoformat(),
            'metrics': {'temperature': 45.0}
        }
        self.assertFalse(self.engine.validate(event))

    def test_invalid_source(self):
        event = {
            'hostname': 'unknown-host',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': {'temperature': 45.0}
        }
        self.assertFalse(self.engine.validate(event))

if __name__ == '__main__':
    unittest.main()
