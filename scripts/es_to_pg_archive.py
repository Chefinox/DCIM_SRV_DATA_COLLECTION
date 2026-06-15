#!/usr/bin/env python3
"""
L13 AI Training Data Archive Script
Migrates historical data from Elasticsearch to PostgreSQL long/EAV table.
"""

import sys
import os
import argparse
import time
from datetime import datetime, timezone, timedelta
import json

# Add project root to path for imports
sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger

import psycopg2
from psycopg2 import extras
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_URL = "https://10.70.0.56:9200"
INDEX = "dcim-metrics-unified-*"
AUTH = ('elastic', 'C+H+pFb*aIAqWcOo-X8q')

PG_PARAMS = {
    "host": "localhost",
    "user": "sot_admin",
    "password": "Inovasi@0918",
    "dbname": "dcim_sot"
}

def extract_fields(doc):
    """
    Extracts numerical metrics from the ES document.
    Returns a list of dicts with field_key and field_value.
    """
    fields = []
    
    # Process dcim_metrics specifically for raw_fields_
    metrics = doc.get("dcim_metrics", {})
    for key, value in metrics.items():
        if key.startswith("raw_fields_") and isinstance(value, (int, float)):
            field_key = key.replace("raw_fields_", "")
            fields.append({
                "field_key": field_key,
                "field_value": float(value),
                "field_value_txt": None
            })
            
    # If no raw_fields_, also look at measurement_name or generic fields
    if not fields:
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                fields.append({
                    "field_key": key,
                    "field_value": float(value),
                    "field_value_txt": None
                })
    return fields

def process_batch(logger, conn, hits):
    if not hits:
        return 0

    records = []
    for hit in hits:
        doc = hit["_source"]
        es_doc_id = hit["_id"]
        
        event_time = doc.get("@timestamp")
        if not event_time:
            continue
            
        tags = doc.get("tag", {})
        device_type = tags.get("device_type", "unknown")
        hostname = tags.get("hostname")
        ip = tags.get("ip")
        serial_number = tags.get("serial_number")
        model = tags.get("model")
        metric_name = tags.get("metric_name", "general_metric")
        enrichment_status = tags.get("enrichment_status")
        raw_source_json = json.dumps(doc)

        fields = extract_fields(doc)
        
        # If no numerical fields are found, we still might want to insert a base record?
        # The EAV model requires field_key. If none, we skip or insert a dummy.
        # It's better to skip if no metrics exist.
        for field in fields:
            record = (
                event_time,
                device_type,
                hostname,
                ip,
                serial_number,
                model,
                metric_name,
                field["field_key"],
                field["field_value"],
                field["field_value_txt"],
                enrichment_status,
                es_doc_id,
                raw_source_json
            )
            records.append(record)

    if not records:
        return 0

    query = """
        INSERT INTO dcim_metrics_archive (
            event_time, device_type, hostname, ip, serial_number, model, metric_name,
            field_key, field_value, field_value_txt, enrichment_status, es_doc_id, raw_source
        ) VALUES %s
        ON CONFLICT (event_time, es_doc_id, field_key) DO NOTHING
    """
    
    try:
        with conn.cursor() as cur:
            extras.execute_values(cur, query, records, page_size=1000)
        conn.commit()
        return len(records)
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert batch to PG: {e}")
        return 0

def run_archive(mode="incremental", dry_run=False):
    logger = setup_logger("dcim-metrics-archive", "/home/infra/dcim_metrics_project/logs/dcim_metrics_archive.log")
    logger.info(f"Starting ES to PG archival job in {mode} mode", extra={"event_type": "archive_start", "mode": mode})

    now_utc = datetime.now(timezone.utc).isoformat()
    
    date_filter = {
        "lte": now_utc
    }
    
    if mode == "incremental":
        # Process last 48 hours for incremental to catch late arrivals
        start_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        date_filter["gte"] = start_time
        
    query = {
        "size": 5000,
        "query": {
            "range": {
                "@timestamp": date_filter
            }
        }
    }

    if dry_run:
        logger.info(f"Dry run query: {json.dumps(query)}")
        return

    total_inserted = 0
    total_docs = 0

    try:
        conn = psycopg2.connect(**PG_PARAMS)
        
        # Init scroll
        res = requests.post(f"{ES_URL}/{INDEX}/_search?scroll=5m", json=query, auth=AUTH, verify=False, timeout=60)
        data = res.json()
        
        if "error" in data:
            logger.error(f"ES Error: {data['error']}", extra={"event_type": "es_query_error"})
            return
            
        scroll_id = data.get("_scroll_id")
        hits = data.get("hits", {}).get("hits", [])
        total_hits = data.get("hits", {}).get("total", {}).get("value", 0)
        
        logger.info(f"Found {total_hits} documents to process.", extra={"event_type": "archive_progress", "total_docs": total_hits})
        
        while hits:
            total_docs += len(hits)
            inserted = process_batch(logger, conn, hits)
            total_inserted += inserted
            
            logger.info(f"Processed {total_docs}/{total_hits} docs. Inserted {total_inserted} EAV rows.")
            
            # Fetch next batch
            res = requests.post(f"{ES_URL}/_search/scroll", json={"scroll": "5m", "scroll_id": scroll_id}, auth=AUTH, verify=False, timeout=60)
            data = res.json()
            hits = data.get("hits", {}).get("hits", [])
            
        logger.info(f"Archival complete. Processed {total_docs} docs, inserted {total_inserted} rows.", extra={"event_type": "archive_complete"})
            
    except Exception as e:
        logger.error(f"Archival failed: {e}", extra={"event_type": "archive_failure"}, exc_info=True)
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["incremental", "backfill"], default="incremental")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    run_archive(args.mode, args.dry_run)
