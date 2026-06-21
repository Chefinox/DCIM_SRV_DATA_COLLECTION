#!/usr/bin/env python3
"""
Setup Kibana Telegram Alert Integration
Creates:
  1. Webhook connector pointing to Telegram Bot API
  2. Alert Rule: ES index tidak diperbarui > 2 jam (pipeline mati)
  3. Alert Rule: Enrichment status NOT_IN_CMDB volume tinggi
  4. Alert Rule: CMDB Drift (hostname != name)

Usage:
  export TELEGRAM_BOT_TOKEN="your_bot_token"
  export TELEGRAM_CHAT_ID="your_chat_id_or_group_id"
  python3 scripts/setup_kibana_telegram_alerts.py
"""

import os
import json
import urllib3
import requests
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KIBANA_URL = "http://10.70.0.56:5601"
ES_URL     = "https://10.70.0.56:9200"
AUTH       = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
HEADERS    = {"kbn-xsrf": "true", "Content-Type": "application/json"}

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("ERROR: Set environment variables TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID before running.")
    print("  export TELEGRAM_BOT_TOKEN='1234567890:ABCDEFxxxxxxxx'")
    print("  export TELEGRAM_CHAT_ID='-1001234567890'")
    sys.exit(1)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def create_telegram_connector():
    """Create Kibana Webhook connector pointed at Telegram."""
    print("Creating Telegram Webhook connector...")
    payload = {
        "name": "DCIM Telegram Alert",
        "connector_type_id": ".webhook",
        "config": {
            "url": TELEGRAM_API_URL,
            "method": "post",
            "headers": {"Content-Type": "application/json"},
            "hasAuth": False
        },
        "secrets": {}
    }
    resp = requests.post(
        f"{KIBANA_URL}/api/actions/connector",
        json=payload, auth=AUTH, headers=HEADERS, verify=False
    )
    if resp.status_code in (200, 201):
        connector_id = resp.json()["id"]
        print(f"  ✅ Connector created: {connector_id}")
        return connector_id
    else:
        print(f"  ❌ Failed: {resp.status_code} {resp.text}")
        return None


def make_telegram_action(connector_id, message_template):
    """Build Kibana action block for Telegram."""
    # Telegram's sendMessage API expects: {"chat_id": "...", "text": "..."}
    return {
        "id": connector_id,
        "group": "default",
        "params": {
            "body": json.dumps({
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message_template,
                "parse_mode": "HTML"
            })
        }
    }


def create_rule_pipeline_down(connector_id):
    """Alert: ES index tidak mendapat data baru selama 2 jam."""
    print("Creating alert: Pipeline Down (no new ES data)...")
    payload = {
        "name": "DCIM: Pipeline Mati - Tidak Ada Data ES 2 Jam",
        "rule_type_id": ".es-query",
        "consumer": "alerts",
        "schedule": {"interval": "30m"},
        "params": {
            "index": ["dcim-metrics-unified-*"],
            "timeField": "@timestamp",
            "timeWindowSize": 2,
            "timeWindowUnit": "h",
            "size": 0,
            "thresholdComparator": "<",
            "threshold": [1],
            "esQuery": json.dumps({
                "query": {"match_all": {}}
            })
        },
        "actions": [make_telegram_action(
            connector_id,
            "🔴 <b>DCIM ALERT: Pipeline Mati!</b>\n"
            "Tidak ada data baru di Elasticsearch selama 2 jam terakhir.\n"
            "Cek: telegraf-consumer, NiFi, atau Kafka broker.\n"
            "Server: 10.70.0.56"
        )]
    }
    resp = requests.post(
        f"{KIBANA_URL}/api/alerting/rule",
        json=payload, auth=AUTH, headers=HEADERS, verify=False
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ Rule created: {resp.json().get('id')}")
    else:
        print(f"  ❌ Failed: {resp.status_code} {resp.text[:300]}")


def create_rule_enrichment_failure(connector_id):
    """Alert: Banyak event dengan enrichment_status NOT_IN_CMDB dalam 1 jam."""
    print("Creating alert: High NOT_IN_CMDB volume...")
    payload = {
        "name": "DCIM: Enrichment Failure Tinggi (NOT_IN_CMDB)",
        "rule_type_id": ".es-query",
        "consumer": "alerts",
        "schedule": {"interval": "30m"},
        "params": {
            "index": ["dcim-metrics-unified-*"],
            "timeField": "@timestamp",
            "timeWindowSize": 1,
            "timeWindowUnit": "h",
            "size": 0,
            "thresholdComparator": ">",
            "threshold": [50],
            "esQuery": json.dumps({
                "query": {
                    "terms": {
                        "tag.enrichment_status.keyword": [
                            "NOT_IN_CMDB",
                            "NO_IDENTIFIER",
                            "ENRICHMENT_ERROR"
                        ]
                    }
                }
            })
        },
        "actions": [make_telegram_action(
            connector_id,
            "⚠️ <b>DCIM ALERT: Enrichment Failure Tinggi!</b>\n"
            "Lebih dari 50 event gagal diperkaya (Enriched) dalam 1 jam.\n"
            "Status Error: NOT_IN_CMDB / NO_IDENTIFIER / ENRICHMENT_ERROR\n"
            "Cek: Konfigurasi Telegraf (Missing Tags) atau Redis Sync API."
        )]
    }
    resp = requests.post(
        f"{KIBANA_URL}/api/alerting/rule",
        json=payload, auth=AUTH, headers=HEADERS, verify=False
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ Rule created: {resp.json().get('id')}")
    else:
        print(f"  ❌ Failed: {resp.status_code} {resp.text[:300]}")


def create_rule_cmdb_drift(connector_id):
    """Alert: Deteksi CMDB Drift (hostname != name dalam enriched events)."""
    print("Creating alert: CMDB Drift detection...")
    payload = {
        "name": "DCIM: CMDB Drift Terdeteksi (hostname != name)",
        "rule_type_id": ".es-query",
        "consumer": "alerts",
        "schedule": {"interval": "1h"},
        "params": {
            "index": ["dcim-metrics-unified-*"],
            "timeField": "@timestamp",
            "timeWindowSize": 1,
            "timeWindowUnit": "h",
            "size": 0,
            "thresholdComparator": ">",
            "threshold": [0],
            "esQuery": json.dumps({
                "query": {
                    "bool": {
                        "must_not": [
                            {"script": {
                                "script": {
                                    "source": "doc['tag.hostname.keyword'].size() > 0 && doc['tag.name.keyword'].size() > 0 && doc['tag.hostname.keyword'].value == doc['tag.name.keyword'].value"
                                }
                            }}
                        ],
                        "filter": [
                            {"exists": {"field": "tag.name.keyword"}},
                            {"exists": {"field": "tag.hostname.keyword"}},
                            {"bool": {"must_not": [{"term": {"tag.name.keyword": ""}}]}}
                        ]
                    }
                }
            })
        },
        "actions": [make_telegram_action(
            connector_id,
            "⚠️ <b>DCIM ALERT: CMDB Drift Terdeteksi!</b>\n"
            "Ada perangkat di mana hostname (fisik) berbeda dari name (CMDB).\n"
            "Ini indikasi data CMDB belum diperbarui atau ada penggantian hostname.\n"
            "Cek Kibana Dashboard → CMDB Compliance"
        )]
    }
    resp = requests.post(
        f"{KIBANA_URL}/api/alerting/rule",
        json=payload, auth=AUTH, headers=HEADERS, verify=False
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ Rule created: {resp.json().get('id')}")
    else:
        print(f"  ❌ Failed: {resp.status_code} {resp.text[:300]}")


def main():
    print("=" * 60)
    print("DCIM Kibana Telegram Alert Setup")
    print("=" * 60)

    connector_id = create_telegram_connector()
    if not connector_id:
        print("\nAborted: Could not create Telegram connector.")
        sys.exit(1)

    print()
    create_rule_pipeline_down(connector_id)
    create_rule_enrichment_failure(connector_id)
    create_rule_cmdb_drift(connector_id)

    print()
    print("=" * 60)
    print("✅ Setup complete!")
    print(f"   Connector ID: {connector_id}")
    print("   Buka Kibana → Stack Management → Rules untuk melihat alert yang dibuat.")
    print("=" * 60)


if __name__ == "__main__":
    main()
