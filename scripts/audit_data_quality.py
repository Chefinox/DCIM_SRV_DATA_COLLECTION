#!/usr/bin/env python3
"""
Data Quality Audit Script (ST-015-05)
Validates Elasticsearch data from the last 24 hours against the required fields in data_quality_schema.yaml.
Logs anomalies to logs/data_quality_YYYYMMDD.log.
"""

import os
import yaml
import json
import urllib3
import requests
from datetime import datetime, timedelta, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_URL = "https://10.70.0.56:9200"
INDEX = "dcim-metrics-unified-*"
AUTH = ('elastic', 'C+H+pFb*aIAqWcOo-X8q')
BASE_DIR = "/home/infra/dcim_metrics_project"

def load_schema():
    schema_path = os.path.join(BASE_DIR, "configs", "data_quality_schema.yaml")
    with open(schema_path, "r") as f:
        return yaml.safe_load(f)

def run_audit(schema):
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    date_str = since_24h.strftime("%Y-%m-%d %H:%M UTC")
    today_str = now.strftime("%Y%m%d")

    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    log_file = os.path.join(BASE_DIR, "logs", f"data_quality_{today_str}.log")

    with open(log_file, "w") as log:
        log.write(f"=== Data Quality Audit (last 24h from {date_str}) ===\n")

        for device_type, required_fields in schema.items():
            # Build exists filters for all required fields
            exists_filters = [{"exists": {"field": field}} for field in required_fields]

            # Base filter: device_type match + rolling 24-hour window
            base_filter = [
                {"term": {"device_type.keyword": device_type}},
                {"range": {
                    "@timestamp": {
                        "gte": "now-24h",
                        "lt": "now"
                    }
                }}
            ]

            # Total documents query
            total_query = {
                "query": {
                    "bool": {
                        "filter": base_filter
                    }
                }
            }

            # Valid documents = total filter + all required fields exist
            valid_query = {
                "query": {
                    "bool": {
                        "filter": base_filter + exists_filters
                    }
                }
            }

            try:
                res_total = requests.post(
                    f"{ES_URL}/{INDEX}/_count",
                    json=total_query, auth=AUTH, verify=False, timeout=30
                )
                res_total.raise_for_status()
                total_docs = res_total.json().get("count", 0)

                res_valid = requests.post(
                    f"{ES_URL}/{INDEX}/_count",
                    json=valid_query, auth=AUTH, verify=False, timeout=30
                )
                res_valid.raise_for_status()
                valid_docs = res_valid.json().get("count", 0)

                percentage = (valid_docs / total_docs * 100) if total_docs > 0 else 0.0

                msg = f"Device: {device_type.upper():<15} | Total: {total_docs:<8} | Valid: {valid_docs:<8} | Completeness: {percentage:.2f}%"
                print(msg)
                log.write(msg + "\n")

                if total_docs == 0:
                    warn_msg = f"  [WARNING] No documents found for {device_type} in the last 24h. Check Telegraf or pipeline."
                    print(warn_msg)
                    log.write(warn_msg + "\n")
                elif percentage < 85.0:
                    anomaly_msg = f"  [WARNING] Completeness for {device_type} is below threshold (85%). Required fields: {required_fields}"
                    print(anomaly_msg)
                    log.write(anomaly_msg + "\n")

            except Exception as e:
                err_msg = f"Error validating {device_type}: {e}"
                print(err_msg)
                log.write(err_msg + "\n")

if __name__ == "__main__":
    schema = load_schema()
    run_audit(schema)
