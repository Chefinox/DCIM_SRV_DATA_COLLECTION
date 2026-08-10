import unittest
import time
from src.validation.engine import ValidationEngine, ValidationResult
from src.validation.rules import RangeRule, FormatRule, FreshnessRule, SourceAllowlistRule

class TestValidationRules(unittest.TestCase):
    def setUp(self):
        self.config = {
            "range": {
                "enabled": True,
                "metrics": {
                    "cpu_usage_percent": {"min": 0, "max": 100}
                }
            },
            "format": {
                "enabled": True,
                "fields": {
                    "ip_address": {"pattern": "^(?:(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(?:25[0-5]|2[0-4]\\d|[01]?\\d\\d?)$"}
                }
            },
            "freshness": {
                "enabled": True,
                "max_staleness_seconds": 300
            },
            "source_allowlist": {
                "enabled": True,
                "allowed_topics": ["dcim.raw.hardware.server"]
            }
        }

    def test_range_rule_valid(self):
        rule = RangeRule(self.config["range"])
        event = {"metric_name": "cpu_usage_percent", "metric_value": 50}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "accepted")

    def test_range_rule_out_of_bounds(self):
        rule = RangeRule(self.config["range"])
        event = {"metric_name": "cpu_usage_percent", "metric_value": 105}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "quarantined")
        self.assertTrue(any("value_out_of_range" in r for r in result.failed_rules))

    def test_range_rule_near_boundary(self):
        rule = RangeRule(self.config["range"])
        event = {"metric_name": "cpu_usage_percent", "metric_value": 95}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "accepted")
        self.assertIn("near_range_boundary", result.quality_flags)

    def test_format_rule_valid(self):
        rule = FormatRule(self.config["format"])
        event = {"raw_fields": {"ip_address": "192.168.1.1"}}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "accepted")

    def test_format_rule_invalid(self):
        rule = FormatRule(self.config["format"])
        event = {"raw_fields": {"ip_address": "999.999.999.999"}}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "quarantined")
        self.assertTrue(any("format_invalid" in r for r in result.failed_rules))

    def test_freshness_rule_stale(self):
        rule = FreshnessRule(self.config["freshness"])
        # Event from 10 minutes ago
        stale_time = time.time() - 600
        event = {"event_time": stale_time}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "quarantined")
        self.assertTrue(any("stale_event" in r for r in result.failed_rules))

    def test_source_allowlist_rule_rejected(self):
        rule = SourceAllowlistRule(self.config["source_allowlist"])
        event = {"source_topic": "malicious.topic"}
        result = ValidationResult()
        rule.validate(event, result)
        self.assertEqual(result.status, "quarantined")
        self.assertTrue(any("source_rejected" in r for r in result.failed_rules))

    def test_engine_dry_run_mode(self):
        engine = ValidationEngine(self.config, dry_run=True)
        # Event that should fail range validation
        event = {
            "metric_name": "cpu_usage_percent", 
            "metric_value": 150,
            "source_topic": "dcim.raw.hardware.server",
            "event_time": time.time()
        }
        result = engine.validate(event)
        # Should be accepted in dry run, but have failure flags
        self.assertEqual(result.status, "accepted")
        self.assertEqual(len(result.failed_rules), 0)
        self.assertTrue(any("dry_run_failure" in f for f in result.quality_flags))

    def test_engine_enforce_mode(self):
        engine = ValidationEngine(self.config, dry_run=False)
        event = {
            "metric_name": "cpu_usage_percent", 
            "metric_value": 150,
            "source_topic": "dcim.raw.hardware.server",
            "event_time": time.time()
        }
        result = engine.validate(event)
        # Should fail in enforce mode
        self.assertEqual(result.status, "quarantined")
        self.assertTrue(len(result.failed_rules) > 0)

if __name__ == '__main__':
    unittest.main()
