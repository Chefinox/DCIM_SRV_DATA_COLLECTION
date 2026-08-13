import unittest
from unittest.mock import patch, MagicMock
from src.validation.dedup import DeduplicationChecker

class TestDeduplicationChecker(unittest.TestCase):
    @patch('redis.Redis')
    def setUp(self, MockRedis):
        self.mock_redis = MockRedis.return_value
        self.checker = DeduplicationChecker()
        
    def test_not_duplicate(self):
        self.mock_redis.setnx.return_value = True
        is_dup = self.checker.is_duplicate("e1", "temp", 45.0, "host1", "sn1")
        self.assertFalse(is_dup)
        self.mock_redis.expire.assert_called_once()
        
    def test_is_duplicate(self):
        self.mock_redis.setnx.return_value = False
        is_dup = self.checker.is_duplicate("e1", "temp", 45.0, "host1", "sn1")
        self.assertTrue(is_dup)
        self.mock_redis.expire.assert_not_called()

if __name__ == '__main__':
    unittest.main()
