#!/usr/bin/env python3
"""
Backfill TimescaleDB metrics from Elasticsearch.

The analytics bridge had a bug where metric_value was not extracted properly,
resulting in all value=0 rows in TimescaleDB. Elasticsearch has the correct
metric_value stored. This script reads from ES using Scroll API and updates
the TimescaleDB rows in bulk.

Strategy:
  - DELETE all value=0 rows from TimescaleDB (they are useless)
  - Re-INSERT correct data from ES with proper metric_value extraction
  - Process in batches using ES scroll API to handle millions of docs

Author: Infra Team (automated backfill)
Date: 2026-07-15
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# --- Configuration ---
ES_URL = os.getenv("ES_URL", "https://10.70.0.56:9200")
ES_USER = os.getenv("ES_USER", "elastic")
ES_PASS = os.getenv("ES_PASS", "C+H+pFb*aIAqWcOo-X8q")
ES_INDEX = "dcim-metrics-unified-*"

TSDB_HOST = os.getenv("TIMESCALE_DB_HOST", "localhost")
TSDB_PORT = os.getenv("TIMESCALE_DB_PORT", "5433")
TSDB_DB = os.getenv("TIMESCALE_DB_NAME", "dcim_analytics")
TSDB_USER = os.getenv("TIMESCALE_DB_USER", "analytics_user")
TSDB_PASS = os.getenv("TIMESCALE_DB_PASS", "changeme")

SCROLL_SIZE = 5000
SCROLL_TIMEOUT = "5m"
BATCH_INSERT_SIZE = 2000

# Metric mapping: how to extract the primary value from raw_fields
# when metric_value is null. Matches configs/metric_mapping.json logic.
METRIC_FIELD_MAP = {
    "interface_status": ["if_oper_status", "ifOperStatus"],
    "disk_temperature": ["diskTemp"],
    "cpu_utilization": ["cpuUtilization", "cpu_utilization"],
    "memory_utilization": ["memoryUsage", "memory_usage"],
    "battery_capacity": ["battery_capacity"],
    "battery_temperature": ["battery_temp"],
    "output_voltage": ["output_voltage"],
    "output_load": ["output_load"],
    "inventory_snapshot": [],  # no numeric value expected
    "general_metric": [],
}


def extract_value(metric_name, metric_value, raw_fields):
    """Extract numeric value using same logic as the fixed bridge."""
    # If ES already has a valid metric_value, use it
    if metric_value is not None:
        try:
            return float(metric_value)
        except (ValueError, TypeError):
            pass

    # Fallback: extract from raw_fields
    if not raw_fields or not isinstance(raw_fields, dict):
        return None

    # Try known field mappings first
    field_keys = METRIC_FIELD_MAP.get(metric_name, [])
    for key in field_keys:
        if key in raw_fields and raw_fields[key] is not None:
            try:
                return float(raw_fields[key])
            except (ValueError, TypeError):
                pass

    # Try exact metric_name match in raw_fields
    if metric_name in raw_fields:
        try:
            return float(raw_fields[metric_name])
        except (ValueError, TypeError):
            pass

    # Last resort: first numeric value
    for v in raw_fields.values():
        if isinstance(v, (int, float)):
            return float(v)

    return None


def extract_unit(metric_name, raw_fields, raw_tags):
    """Extract unit from context."""
    unit_map = {
        "interface_status": "status_code",
        "disk_temperature": "celsius",
        "cpu_utilization": "percent",
        "memory_utilization": "percent",
        "battery_capacity": "percent",
        "battery_temperature": "celsius",
        "output_voltage": "volt",
        "output_load": "percent",
    }
    return unit_map.get(metric_name)


def connect_tsdb():
    """Connect to TimescaleDB."""
    conn = psycopg2.connect(
        host=TSDB_HOST, port=TSDB_PORT,
        database=TSDB_DB, user=TSDB_USER, password=TSDB_PASS
    )
    conn.autocommit = False
    return conn


def delete_zero_rows(conn):
    """Delete all rows where value=0 (the broken data)."""
    log.info("Deleting all value=0 rows from TimescaleDB metrics table...")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM metrics WHERE value = 0;")
        count = cur.fetchone()[0]
        log.info(f"Found {count:,} rows with value=0 to delete")

        if count == 0:
            log.info("No zero-value rows to delete. Skipping.")
            return 0

        # Delete in chunks to avoid long locks
        total_deleted = 0
        while True:
            cur.execute("""
                DELETE FROM metrics
                WHERE ctid IN (
                    SELECT ctid FROM metrics WHERE value = 0 LIMIT 50000
                );
            """)
            deleted = cur.rowcount
            conn.commit()
            total_deleted += deleted
            log.info(f"  Deleted chunk: {deleted} rows (total: {total_deleted:,})")
            if deleted < 50000:
                break

        log.info(f"Total deleted: {total_deleted:,} zero-value rows")
        return total_deleted


def scroll_es(session):
    """Generator that yields ES documents via scroll API."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "metric_name"}},
                    {"exists": {"field": "event_time"}}
                ]
            }
        },
        "_source": [
            "event_time", "metric_name", "metric_value",
            "raw_fields", "raw_tags", "device_type", "hostname",
            "ci_id", "asset_id", "serial_number", "metric_unit"
        ],
        "sort": [{"event_time": "asc"}]
    }

    # Initial search
    resp = session.post(
        f"{ES_URL}/{ES_INDEX}/_search?scroll={SCROLL_TIMEOUT}&size={SCROLL_SIZE}",
        json=query, verify=False
    )
    resp.raise_for_status()
    data = resp.json()

    scroll_id = data.get("_scroll_id")
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    log.info(f"ES scroll started. Total docs to process: {total:,}")

    while hits:
        for hit in hits:
            yield hit["_source"]

        # Next scroll
        resp = session.post(
            f"{ES_URL}/_search/scroll",
            json={"scroll": SCROLL_TIMEOUT, "scroll_id": scroll_id},
            verify=False
        )
        resp.raise_for_status()
        data = resp.json()
        scroll_id = data.get("_scroll_id")
        hits = data.get("hits", {}).get("hits", [])

    # Clear scroll
    try:
        session.delete(
            f"{ES_URL}/_search/scroll",
            json={"scroll_id": scroll_id},
            verify=False
        )
    except Exception:
        pass


def backfill():
    """Main backfill process."""
    log.info("=" * 60)
    log.info("BACKFILL START: ES → TimescaleDB")
    log.info("=" * 60)

    # Step 1: Connect
    conn = connect_tsdb()
    session = requests.Session()
    session.auth = (ES_USER, ES_PASS)

    # Step 2: Delete broken zero-value rows
    delete_zero_rows(conn)

    # Step 3: Scroll ES and insert correct data
    batch = []
    total_inserted = 0
    skipped = 0
    start_time = time.time()

    for doc in scroll_es(session):
        metric_name = doc.get("metric_name")
        event_time = doc.get("event_time")
        raw_fields = doc.get("raw_fields", {})
        raw_tags = doc.get("raw_tags", {})
        metric_value_es = doc.get("metric_value")

        if not event_time or not metric_name:
            skipped += 1
            continue

        value = extract_value(metric_name, metric_value_es, raw_fields)
        if value is None:
            skipped += 1
            continue

        unit = extract_unit(metric_name, raw_fields, raw_tags) or doc.get("metric_unit")

        # Build tags JSONB
        tags = {}
        if isinstance(raw_tags, dict):
            tags = raw_tags
        if isinstance(raw_fields, dict):
            # Add select raw_fields for richer context
            for k in ("if_name", "diskModel", "psu", "fan", "sensor"):
                if k in raw_fields:
                    tags[k] = raw_fields[k]

        source = doc.get("device_type", "unknown")

        row = (
            event_time,
            metric_name,
            doc.get("ci_id"),
            doc.get("asset_id"),
            source,
            value,
            unit,
            json.dumps(tags)
        )
        batch.append(row)

        if len(batch) >= BATCH_INSERT_SIZE:
            inserted = flush_batch(conn, batch)
            total_inserted += inserted
            batch = []

            elapsed = time.time() - start_time
            rate = total_inserted / elapsed if elapsed > 0 else 0
            log.info(
                f"Progress: {total_inserted:,} inserted, {skipped:,} skipped "
                f"({rate:.0f} rows/sec)"
            )

    # Flush remaining
    if batch:
        inserted = flush_batch(conn, batch)
        total_inserted += inserted

    elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info(f"BACKFILL COMPLETE")
    log.info(f"  Total inserted: {total_inserted:,}")
    log.info(f"  Total skipped:  {skipped:,}")
    log.info(f"  Duration:       {elapsed:.1f}s ({elapsed/60:.1f}m)")
    log.info("=" * 60)

    conn.close()
    session.close()


def flush_batch(conn, batch):
    """Insert a batch of rows into TimescaleDB."""
    try:
        query = """
            INSERT INTO metrics (time, metric_name, ci_id, asset_id, source, value, unit, tags)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        with conn.cursor() as cur:
            execute_values(cur, query, batch, page_size=1000)
        conn.commit()
        return len(batch)
    except Exception as e:
        log.error(f"Failed to insert batch: {e}")
        conn.rollback()
        return 0


if __name__ == "__main__":
    backfill()
