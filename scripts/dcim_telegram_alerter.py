#!/usr/bin/env python3
"""
DCIM Pipeline Health Alerter via Telegram
Replaces Kibana Actions (requires Gold license) with a standalone Python script.

Checks:
  1. Pipeline mati — tidak ada data baru di ES > 2 jam
  2. Enrichment failure tinggi — banyak NOT_IN_CMDB dalam 1 jam
  3. CMDB Drift — hostname != name dalam enriched events
  4. DLQ spike — terlalu banyak pesan error dalam 30 menit

Runs every 5 minutes via systemd timer: dcim-telegram-alerter.timer
"""

import os
import json
import requests
import urllib3
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger
logger = setup_logger("telegram-alerter", "/home/infra/dcim_metrics_project/logs/dcim_telegram_alerter.log")

# === CONFIG ===
ES_URL   = "https://10.70.0.56:9200"
ES_AUTH  = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
ES_INDEX = "dcim-metrics-unified-*"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8320149476:AAFy2G5ma1YQnQeIC-PBuwFH1xxiKO38JF4")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "-5266403936")
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Cooldown: simpan state alert terakhir agar tidak spam
STATE_FILE = "/home/infra/dcim_metrics_project/logs/telegram_alerter_state.json"


def send_telegram(message: str):
    """Kirim notifikasi ke grup Telegram."""
    try:
        resp = requests.post(TELEGRAM_API, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        return resp.ok
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def es_count(query: dict) -> int:
    """Hitung jumlah dokumen di ES sesuai query."""
    try:
        resp = requests.post(
            f"{ES_URL}/{ES_INDEX}/_count",
            json=query, auth=ES_AUTH, verify=False, timeout=30
        )
        return resp.json().get("count", 0)
    except Exception as e:
        logger.error(f"ES count failed: {e}")
        return -1


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def is_cooldown(state: dict, alert_key: str, cooldown_minutes: int = 60) -> bool:
    """Cek apakah alert ini sudah dikirim dalam periode cooldown (agar tidak spam)."""
    last_sent = state.get(alert_key)
    if not last_sent:
        return False
    last_dt = datetime.fromisoformat(last_sent)
    elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
    return elapsed < cooldown_minutes


def check_pipeline_alive(state: dict) -> list:
    """ST-017-02a: Tidak ada data baru di ES selama 2 jam."""
    alerts = []
    count = es_count({"query": {"range": {"@timestamp": {"gte": "now-2h"}}}})
    if count == 0 and not is_cooldown(state, "pipeline_down", cooldown_minutes=120):
        msg = (
            "🔴 <b>DCIM KRITIS: Pipeline Mati!</b>\n\n"
            "Tidak ada data baru masuk ke Elasticsearch dalam <b>2 jam terakhir</b>.\n\n"
            "Kemungkinan penyebab:\n"
            "• Service <code>telegraf-consumer</code> mati\n"
            "• Kafka broker tidak dapat dijangkau\n"
            "• NiFi flow berhenti\n\n"
            "⚡ <b>Aksi:</b> <code>systemctl status telegraf-consumer</code>\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M WIB')}"
        )
        alerts.append(("pipeline_down", msg))
    elif count > 0:
        # Reset state jika pipeline sudah hidup kembali
        if state.get("pipeline_down"):
            del state["pipeline_down"]
    return alerts


def check_enrichment_failure(state: dict) -> list:
    """ST-017-02b: Banyak NOT_IN_CMDB dalam 1 jam terakhir."""
    alerts = []
    THRESHOLD = 50
    count = es_count({
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tag.enrichment_status.keyword": "NOT_IN_CMDB"}},
                    {"range": {"@timestamp": {"gte": "now-1h"}}}
                ]
            }
        }
    })
    if count > THRESHOLD and not is_cooldown(state, "enrichment_failure", cooldown_minutes=60):
        msg = (
            "⚠️ <b>DCIM WARNING: Enrichment Failure Tinggi!</b>\n\n"
            f"<b>{count}</b> event dengan status <code>NOT_IN_CMDB</code> dalam 1 jam terakhir.\n"
            f"(Threshold: {THRESHOLD} event)\n\n"
            "Kemungkinan penyebab:\n"
            "• Redis cache tidak sinkron dengan iTop\n"
            "• Ada perangkat baru yang belum terdaftar di CMDB\n\n"
            "⚡ <b>Aksi:</b> <code>systemctl restart dcim-itop-redis-sync</code>\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M WIB')}"
        )
        alerts.append(("enrichment_failure", msg))
    return alerts


def check_cmdb_drift(state: dict) -> list:
    """ST-017-03: Hostname fisik berbeda dengan name di CMDB."""
    alerts = []
    # Cek device yang punya 'name' berbeda dari 'hostname'
    # Menggunakan script query untuk membandingkan dua field
    count = es_count({
        "query": {
            "bool": {
                "filter": [
                    {"exists": {"field": "tag.name.keyword"}},
                    {"range": {"@timestamp": {"gte": "now-1h"}}},
                    # Pastikan name tidak kosong
                    {"bool": {"must_not": [{"term": {"tag.name.keyword": ""}}]}}
                ],
                "must_not": [
                    {"script": {
                        "script": {
                            "lang": "painless",
                            "source": (
                                "doc['tag.hostname.keyword'].size() > 0 && "
                                "doc['tag.name.keyword'].size() > 0 && "
                                "doc['tag.hostname.keyword'].value == doc['tag.name.keyword'].value"
                            )
                        }
                    }}
                ]
            }
        }
    })
    if count > 0 and not is_cooldown(state, "cmdb_drift", cooldown_minutes=360):  # max 1x per 6 jam
        msg = (
            "⚠️ <b>DCIM INFO: CMDB Drift Terdeteksi!</b>\n\n"
            f"<b>{count}</b> event di mana <code>hostname</code> (fisik) "
            "berbeda dari <code>name</code> (CMDB) dalam 1 jam terakhir.\n\n"
            "Ini mengindikasikan data CMDB belum diperbarui atau ada perubahan hostname.\n\n"
            "⚡ <b>Aksi:</b> Cek Kibana Dashboard → CMDB Compliance\n"
            f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M WIB')}"
        )
        alerts.append(("cmdb_drift", msg))
    return alerts


def check_dlq_spike(state: dict) -> list:
    """ST-017-02d: Lonjakan pesan DLQ dalam 30 menit terakhir."""
    alerts = []
    THRESHOLD = 100
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", database="dcim_sot",
            user="sot_admin", password="Inovasi@0918"
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM dlq_records WHERE received_at > NOW() - INTERVAL '30 minutes'"
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()

        if count > THRESHOLD and not is_cooldown(state, "dlq_spike", cooldown_minutes=30):
            msg = (
                "🔴 <b>DCIM WARNING: DLQ Spike!</b>\n\n"
                f"<b>{count}</b> pesan gagal (DLQ) dalam 30 menit terakhir.\n"
                f"(Threshold: {THRESHOLD} pesan)\n\n"
                "Kemungkinan penyebab:\n"
                "• Format payload dari Telegraf berubah\n"
                "• Error di normalizer atau enrichment service\n\n"
                "⚡ <b>Aksi:</b> <code>tail -100 logs/dcim_dlq_consumer.log</code>\n"
                f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M WIB')}"
            )
            alerts.append(("dlq_spike", msg))
    except Exception as e:
        logger.warning(f"DLQ check skipped: {e}")
    return alerts


def main():
    logger.info("Running DCIM Telegram Alerter...")

    state = load_state()
    all_alerts = []

    all_alerts.extend(check_pipeline_alive(state))
    all_alerts.extend(check_enrichment_failure(state))
    all_alerts.extend(check_cmdb_drift(state))
    all_alerts.extend(check_dlq_spike(state))

    if not all_alerts:
        logger.info("All checks passed. No alerts.")
    else:
        for alert_key, msg in all_alerts:
            logger.info(f"Sending alert: {alert_key}")
            if send_telegram(msg):
                state[alert_key] = datetime.now(timezone.utc).isoformat()
                logger.info(f"Sent {alert_key} successfully.")
            else:
                logger.error(f"Failed to send {alert_key}.")

    save_state(state)
    logger.info("Done.")


if __name__ == "__main__":
    main()
