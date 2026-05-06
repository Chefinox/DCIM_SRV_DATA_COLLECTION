import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from src.configs.database import get_db_config
import logging

class PostgresClient:
    def __init__(self, config=None):
        self.config = config or get_db_config()
        self.conn = None

    def connect(self):
        if not self.conn or self.conn.closed:
            try:
                self.conn = psycopg2.connect(**self.config)
                self.conn.autocommit = True
            except Exception as e:
                logging.error(f"PostgreSQL Connection Error: {e}")
                raise
        return self.conn

    def execute_query(self, query, params=None, fetch=True):
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            return None

    def execute_batch(self, queries_with_params):
        """
        Executes multiple queries in a single transaction.
        queries_with_params: list of (query_string, params_tuple)
        """
        conn = self.connect()
        with conn.cursor() as cur:
            for query, params in queries_with_params:
                cur.execute(query, params)

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
