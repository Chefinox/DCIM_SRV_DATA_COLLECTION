import hashlib
import redis

class DeduplicationChecker:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, ttl=60):
        self.ttl = ttl
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

    def is_duplicate(self, event_id: str, metric_name: str, metric_value: float, hostname: str, serial_number: str) -> bool:
        # Generate hash based on content
        content_string = f"{event_id}:{metric_name}:{metric_value}:{hostname}:{serial_number}"
        content_hash = hashlib.sha256(content_string.encode('utf-8')).hexdigest()
        
        # Check and set in redis
        key = f"dedup:{content_hash}"
        # setnx returns True if key didn't exist and was set, False if it existed
        is_new = self.redis_client.setnx(key, "1")
        if is_new:
            self.redis_client.expire(key, self.ttl)
            return False # Not a duplicate
        return True # Duplicate
