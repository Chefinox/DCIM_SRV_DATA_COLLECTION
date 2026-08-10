"""Deduplication logic using Redis sliding window."""
import time
import hashlib
import redis
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DeduplicationChecker:
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get("enabled", False)
        self.window_seconds = config.get("window_seconds", 60)
        
        if self.enabled:
            # Connect to Redis
            try:
                host = config.get("redis_host", "localhost")
                port = config.get("redis_port", 6379)
                db = config.get("redis_db", 1)
                
                # In production, credentials would be injected via env/Vault
                # Here we use the unauthenticated local connection as configured in dcim-metrics-project
                self.redis_client = redis.Redis(
                    host=host, 
                    port=port, 
                    db=db,
                    decode_responses=True
                )
                self.redis_client.ping()
                logger.info(f"Deduplication Redis connected (db={db}, window={self.window_seconds}s)")
            except Exception as e:
                logger.error(f"Failed to connect to Redis for deduplication: {e}")
                self.enabled = False
                
    def _generate_hash(self, event: Dict[str, Any]) -> str:
        """Generate SHA-256 hash of core event fields."""
        # Use key fields that uniquely identify the state
        key_fields = [
            str(event.get("hostname", "")),
            str(event.get("serial_number", "")),
            str(event.get("metric_name", "")),
            str(event.get("metric_value", ""))
        ]
        
        content = ":".join(key_fields)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
        
    def is_duplicate(self, event: Dict[str, Any]) -> bool:
        """
        Check if event is a duplicate.
        Returns True if it's a duplicate, False otherwise.
        """
        if not self.enabled:
            return False
            
        content_hash = self._generate_hash(event)
        redis_key = f"dedup:{content_hash}"
        
        try:
            # SETNX (set if not exists)
            # Returns 1 if key was set (new event), 0 if key already exists (duplicate)
            is_new = self.redis_client.setnx(redis_key, "1")
            
            if is_new:
                # Set TTL for the sliding window
                self.redis_client.expire(redis_key, self.window_seconds)
                return False
            else:
                return True
                
        except Exception as e:
            logger.error(f"Redis dedup check failed: {e}")
            # Fail open (accept event) if Redis is down
            return False
