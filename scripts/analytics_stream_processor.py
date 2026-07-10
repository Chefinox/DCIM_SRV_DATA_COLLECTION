#!/usr/bin/env python3
"""
Analytics Stream Processor
Consumes metrics from dcim.analytics.metrics Kafka topic and inserts into TimescaleDB
"""

import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values
from kafka import KafkaConsumer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TIMESCALE_DB_HOST = os.getenv('TIMESCALE_DB_HOST', 'localhost')
TIMESCALE_DB_PORT = os.getenv('TIMESCALE_DB_PORT', '5433')
TIMESCALE_DB_NAME = os.getenv('TIMESCALE_DB_NAME', 'dcim_analytics')
TIMESCALE_DB_USER = os.getenv('TIMESCALE_DB_USER', 'analytics_user')
TIMESCALE_DB_PASS = os.getenv('TIMESCALE_DB_PASS', 'changeme')

# Kafka topics
METRICS_TOPIC = 'dcim.analytics.metrics'
ANOMALIES_TOPIC = 'dcim.analytics.anomalies'
PREDICTIONS_TOPIC = 'dcim.analytics.predictions'

# Consumer group
CONSUMER_GROUP = 'analytics-stream-processor'


class TimescaleDBWriter:
    """Writer for TimescaleDB metrics table"""
    
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Establish connection to TimescaleDB"""
        try:
            self.conn = psycopg2.connect(
                host=TIMESCALE_DB_HOST,
                port=TIMESCALE_DB_PORT,
                database=TIMESCALE_DB_NAME,
                user=TIMESCALE_DB_USER,
                password=TIMESCALE_DB_PASS
            )
            self.conn.autocommit = True
            logger.info(f"Connected to TimescaleDB at {TIMESCALE_DB_HOST}:{TIMESCALE_DB_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            raise
    
    def insert_metrics(self, metrics: list) -> int:
        """Bulk insert metrics into TimescaleDB"""
        if not metrics:
            return 0
        
        try:
            query = """
                INSERT INTO metrics (time, metric_name, ci_id, asset_id, source, value, unit, tags)
                VALUES %s
                ON CONFLICT DO NOTHING
            """
            values = [
                (
                    m.get('time'),
                    m.get('metric_name'),
                    m.get('ci_id'),
                    m.get('asset_id'),
                    m.get('source'),
                    m.get('value'),
                    m.get('unit'),
                    json.dumps(m.get('tags', {}))
                )
                for m in metrics
            ]
            
            with self.conn.cursor() as cur:
                execute_values(cur, query, values, page_size=1000)
            
            return len(values)
        except Exception as e:
            logger.error(f"Failed to insert metrics: {e}")
            return 0
    
    def close(self):
        """Close connection"""
        if self.conn:
            self.conn.close()


class AnalyticsStreamProcessor:
    """Main stream processor for AI analytics"""
    
    def __init__(self):
        self.running = False
        self.consumer = None
        self.writer = None
        self.metrics_buffer = []
        self.buffer_size = 100
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _create_consumer(self) -> KafkaConsumer:
        """Create Kafka consumer"""
        return KafkaConsumer(
            METRICS_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            consumer_timeout_ms=1000,
            security_protocol='SSL',
            ssl_cafile='/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
            ssl_check_hostname=False
        )
    
    def _process_message(self, message):
        """Process a single Kafka message"""
        try:
            data = message.value
            
            # Transform to TimescaleDB format
            metric = {
                'time': data.get('timestamp') or datetime.now(timezone.utc).isoformat(),
                'metric_name': data.get('metric_name', data.get('measurement', 'unknown')),
                'ci_id': data.get('ci_id'),
                'asset_id': data.get('asset_id'),
                'source': data.get('source', data.get('device_type', 'unknown')),
                'value': float(data.get('metric_value', data.get('value', 0))),
                'unit': data.get('metric_unit', data.get('unit')),
                'tags': data.get('tags', {})
            }
            
            return metric
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            return None
    
    def _flush_buffer(self):
        """Flush metrics buffer to TimescaleDB"""
        if self.metrics_buffer:
            try:
                count = self.writer.insert_metrics(self.metrics_buffer)
                logger.info(f"Inserted {count} metrics to TimescaleDB")
            except Exception as e:
                logger.error(f"Failed to flush buffer: {e}")
            finally:
                self.metrics_buffer = []
    
    def start(self):
        """Start the stream processor"""
        logger.info("Starting Analytics Stream Processor...")
        
        self.writer = TimescaleDBWriter()
        self.consumer = self._create_consumer()
        self.running = True
        
        logger.info(f"Consuming from topic: {METRICS_TOPIC}")
        
        try:
            while self.running:
                try:
                    messages = self.consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, records in messages.items():
                        for record in records:
                            metric = self._process_message(record)
                            if metric:
                                self.metrics_buffer.append(metric)
                                
                                # Flush when buffer is full
                                if len(self.metrics_buffer) >= self.buffer_size:
                                    self._flush_buffer()
                    
                    # Flush remaining buffer
                    if self.metrics_buffer:
                        self._flush_buffer()
                        
                except Exception as e:
                    logger.error(f"Error in processing loop: {e}")
                    
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            self._flush_buffer()
            self.consumer.close()
            self.writer.close()
            logger.info("Analytics Stream Processor stopped")


if __name__ == '__main__':
    processor = AnalyticsStreamProcessor()
    processor.start()