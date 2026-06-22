#!/usr/bin/env python3
import sys
import json
import time
from datetime import datetime, timezone
import psycopg2

sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger
from kafka import KafkaConsumer

PG_PARAMS = {
    "host": "localhost",
    "user": "sot_admin",
    "password": "Inovasi@0918",
    "dbname": "dcim_sot"
}

logger = setup_logger("anomaly-inference", "/home/infra/dcim_metrics_project/logs/anomaly_inference.log")

def dummy_isolation_forest_predict(features):
    # Mock model: anomaly if cpu > 90 or mem > 95 or temp > 80
    cpu = features.get("cpu_util_pct", 0)
    mem = features.get("mem_util_pct", 0)
    temp = features.get("temp_celsius", 0)
    
    if cpu > 90 or mem > 95 or temp > 80:
        return True, 0.95
    return False, 0.1

def process_message(msg_value, conn):
    try:
        data = json.loads(msg_value)
        tags = data.get("tag", {})
        
        # Only process server events for anomaly
        if tags.get("device_type") != "server":
            return
            
        metrics = data.get("dcim_metrics", {})
        
        # In actual implementation, we might do forward-fill by querying previous row
        # Here we just use the raw values
        
        # Try to extract the same fields we put in v_train_server
        cpu_util = metrics.get("cpu_utilization")
        if cpu_util is None and "raw_fields_cpu_utilization" in metrics:
             cpu_util = metrics["raw_fields_cpu_utilization"]

        mem_util = metrics.get("memory_usage")
        if mem_util is None and "raw_fields_memory_usage" in metrics:
             mem_util = metrics["raw_fields_memory_usage"]
             
        temp = metrics.get("reading_celsius")
        if temp is None and "raw_fields_reading_celsius" in metrics:
             temp = metrics["raw_fields_reading_celsius"]
             
        power = metrics.get("power_output_watts")
        if power is None and "raw_fields_power_output_watts" in metrics:
             power = metrics["raw_fields_power_output_watts"]
             
        # Mock imputation (median fill if None)
        cpu_util = float(cpu_util) if cpu_util is not None else 50.0
        mem_util = float(mem_util) if mem_util is not None else 50.0
        temp = float(temp) if temp is not None else 25.0
        power = float(power) if power is not None else 200.0
        
        features = {
            "cpu_util_pct": cpu_util,
            "mem_util_pct": mem_util,
            "temp_celsius": temp,
            "power_watts": power
        }
        
        is_anomaly, score = dummy_isolation_forest_predict(features)
        
        event_time = data.get("@timestamp")
        hostname = tags.get("hostname")
        serial_number = tags.get("serial_number")
        
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dcim_server_anomalies (
                    event_time, hostname, serial_number,
                    cpu_util_pct, mem_util_pct, temp_celsius, power_watts,
                    anomaly, anomaly_score, model_version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (event_time, hostname, serial_number, cpu_util, mem_util, temp, power, is_anomaly, score, "mock_v1")
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        if conn:
            conn.rollback()

def run_consumer():
    consumer = KafkaConsumer(
        "dcim.enriched.events",
        bootstrap_servers=["127.0.0.1:9092"],
        group_id="dcim-ai-inference",
        auto_offset_reset="latest"
    )
    
    logger.info("Starting anomaly inference consumer")
    
    conn = None
    try:
        conn = psycopg2.connect(**PG_PARAMS)
        for msg in consumer:
            process_message(msg.value.decode("utf-8"), conn)
    except Exception as e:
        logger.error(f"Consumer error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    run_consumer()
