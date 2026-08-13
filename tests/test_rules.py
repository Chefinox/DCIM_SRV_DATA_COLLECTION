import unittest
from src.validation.rules import BaseRule, FormatRule

class TestBaseRule(unittest.TestCase):
    def test_base_rule_raises(self):
        rule = BaseRule()
        with self.assertRaises(NotImplementedError):
            rule.validate({})
            
class TestFormatRule(unittest.TestCase):
    def test_format_rule_missing_hostname(self):
        rule = FormatRule()
        self.assertFalse(rule.validate({'timestamp': 'xxx', 'metrics': {}}))
        
if __name__ == '__main__':
    unittest.main()
