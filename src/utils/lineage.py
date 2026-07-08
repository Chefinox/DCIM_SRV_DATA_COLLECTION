import psycopg2
from psycopg2 import pool
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from src.utils.secrets import get_secret
import atexit

logger = logging.getLogger(__name__)

_pool = None

def get_pool():
    global _pool
    if _pool is None:
        try:
            db_pass = get_secret("postgres", "password")
            if not db_pass:
                db_pass = os.environ.get("SOT_DB_PASS", "")
                
            _pool = pool.ThreadedConnectionPool(
                1, 20,
                host="10.70.0.56",
                database="dcim_sot",
                user="sot_admin",
                password=db_pass
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
    return _pool

@atexit.register
def close_pool():
    if _pool is not None:
        _pool.closeall()

class LineageTracker:
    def __init__(self):
        self.pool = get_pool()
        
    def _execute_update(self, query: str, params: tuple):
        if not self.pool:
            return False
        conn = None
        try:
            conn = self.pool.getconn()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to execute lineage update: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                self.pool.putconn(conn)
                
    def create_lineage(self, event_id: str, source_system: str = None):
        """Create new lineage record when event is first seen."""
        query = """
            INSERT INTO event_lineage (lineage_id, event_id, source_system, ingested_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (lineage_id) DO NOTHING
        """
        return self._execute_update(query, (event_id, event_id, source_system, datetime.now(timezone.utc)))

    def update_validation(self, event_id: str, status: str, error: str = None, processing_ms: int = 0):
        query = """
            UPDATE event_lineage 
            SET validation_status = %s, validated_at = %s, validation_error = %s,
                processing_ms_total = COALESCE(processing_ms_total, 0) + %s
            WHERE event_id = %s
        """
        self._execute_update(query, (status, datetime.now(timezone.utc), error, processing_ms, event_id))

    def update_enrichment(self, event_id: str, status: str, error: str = None, processing_ms: int = 0):
        query = """
            UPDATE event_lineage 
            SET enrichment_status = %s, enriched_at = %s, enrichment_error = %s,
                processing_ms_total = COALESCE(processing_ms_total, 0) + %s
            WHERE event_id = %s
        """
        self._execute_update(query, (status, datetime.now(timezone.utc), error, processing_ms, event_id))

    def update_routing(self, event_id: str, target_store: str, target_id: str = None, processing_ms: int = 0):
        query = """
            UPDATE event_lineage 
            SET routing_status = 'routed', routed_at = %s, target_store = %s, target_id = %s,
                processing_ms_total = COALESCE(processing_ms_total, 0) + %s
            WHERE event_id = %s
        """
        self._execute_update(query, (datetime.now(timezone.utc), target_store, target_id, processing_ms, event_id))

# Kept for backwards compatibility if needed, but redirects to the new class
def track_lineage(event_id: str, stage: str, status: str, source_system: str = None, source_topic: str = None, target_topic: str = None, error_message: str = None, processing_ms: int = 0, metadata: dict = None):
    tracker = LineageTracker()
    if stage == "ingested" or stage == "normalized" and status != "dlq":
        tracker.create_lineage(event_id, source_system)
        tracker.update_validation(event_id, status, error_message, processing_ms or 0)
    elif stage == "normalized" and status == "dlq":
        tracker.create_lineage(event_id, source_system)
        tracker.update_validation(event_id, status, error_message, processing_ms or 0)
    elif stage == "enriched":
        tracker.update_enrichment(event_id, status, error_message, processing_ms or 0)
    elif stage == "routed" or stage == "stored":
        tracker.update_routing(event_id, target_topic or "unknown", None, processing_ms or 0)
