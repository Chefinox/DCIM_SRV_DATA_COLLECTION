"""Rate limiting and concurrency control for pollers."""
import time
import threading
import logging
from typing import Dict, Any, Optional
import random

logger = logging.getLogger(__name__)

class PollRateLimiter:
    """
    Enforces concurrency limits and rate ceilings per source system.
    Follows ADR-0023 source-impact controls.
    """
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = {}
            
        self.max_concurrent = config.get("max_concurrent", 2)
        self.max_req_per_min = config.get("max_req_per_min", 10)
        
        # Concurrency control
        self._semaphore = threading.Semaphore(self.max_concurrent)
        
        # Rate limiting (Token Bucket)
        self._tokens = float(self.max_req_per_min)
        self._last_refill = time.time()
        self._refill_rate = self.max_req_per_min / 60.0  # tokens per second
        self._lock = threading.Lock()
        
    def _refill(self):
        now = time.time()
        time_passed = now - self._last_refill
        
        if time_passed > 0:
            new_tokens = time_passed * self._refill_rate
            self._tokens = min(self.max_req_per_min, self._tokens + new_tokens)
            self._last_refill = now
            
    def acquire(self, timeout_sec: float = 5.0) -> bool:
        """
        Wait until both concurrency slot and rate token are available.
        Returns True if acquired within timeout, False if timeout reached.
        """
        start_time = time.time()
        
        # 1. Acquire concurrency slot
        if not self._semaphore.acquire(timeout=timeout_sec):
            logger.warning(f"RateLimiter: Timed out waiting for concurrency slot ({timeout_sec}s)")
            return False
            
        # 2. Acquire rate token
        while True:
            # Check remaining time
            elapsed = time.time() - start_time
            if elapsed >= timeout_sec:
                self._semaphore.release()
                logger.warning(f"RateLimiter: Timed out waiting for rate token ({timeout_sec}s)")
                return False
                
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                    
            # If no token, wait a bit with jitter
            # Decorrelated jitter backoff
            sleep_time = min(1.0, random.uniform(0.1, 0.5))
            time.sleep(sleep_time)
            
    def release(self):
        """Release the concurrency slot."""
        self._semaphore.release()
        
    def __enter__(self):
        # When used as context manager, we wait indefinitely (or raise exception if we want strict timeout)
        # For simplicity, we wait up to 30s
        acquired = self.acquire(timeout_sec=30.0)
        if not acquired:
            raise TimeoutError("Failed to acquire rate limit slot within 30s")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

# Global registry for per-source limiters
_limiters: Dict[str, PollRateLimiter] = {}
_registry_lock = threading.Lock()

def get_limiter(source_ip: str, config: Dict[str, Any] = None) -> PollRateLimiter:
    """Get or create a rate limiter for a specific source IP/hostname."""
    with _registry_lock:
        if source_ip not in _limiters:
            _limiters[source_ip] = PollRateLimiter(config)
        return _limiters[source_ip]
