import unittest
from unittest.mock import MagicMock, patch
from src.validation.dedup import DeduplicationChecker

class TestDeduplication(unittest.TestCase):
    @patch('src.validation.dedup.redis.Redis')
    def test_dedup_new_event(self, mock_redis_class):
        # Setup mock
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = 1  # 1 means key was set (new)
        mock_redis_class.return_value = mock_redis
        
        config = {
            "enabled": True,
            "window_seconds": 60
        }
        
        checker = DeduplicationChecker(config)
        event = {
            "hostname": "server1",
            "metric_name": "cpu_usage",
            "metric_value": 50
        }
        
        # Should NOT be duplicate
        self.assertFalse(checker.is_duplicate(event))
        mock_redis.setnx.assert_called_once()
        mock_redis.expire.assert_called_once_with(mock_redis.setnx.call_args[0][0], 60)

    @patch('src.validation.dedup.redis.Redis')
    def test_dedup_duplicate_event(self, mock_redis_class):
        # Setup mock
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = 0  # 0 means key exists (duplicate)
        mock_redis_class.return_value = mock_redis
        
        config = {"enabled": True}
        checker = DeduplicationChecker(config)
        
        event = {"metric_name": "cpu_usage", "metric_value": 50}
        
        # SHOULD be duplicate
        self.assertTrue(checker.is_duplicate(event))
        mock_redis.expire.assert_not_called()

if __name__ == '__main__':
    unittest.main()
