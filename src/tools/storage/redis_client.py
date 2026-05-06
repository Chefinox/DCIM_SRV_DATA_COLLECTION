import redis
import os
import json
import logging
from src.configs.loader import read_secret

class RedisClient:
    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.password = read_secret("REDIS_PASS")
        self.client = None

    def connect(self):
        if not self.client:
            try:
                self.client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    decode_responses=True,
                    socket_timeout=5
                )
            except Exception as e:
                logging.error(f"Redis Connection Error: {e}")
                raise
        return self.client

    def get_json(self, key):
        data = self.connect().get(key)
        return json.loads(data) if data else None

    def set_json(self, key, value, ex=86400):
        return self.connect().set(key, json.dumps(value), ex=ex)
