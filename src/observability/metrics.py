"""Prometheus metrics for the DCIM pipeline."""
from prometheus_client import Counter, Histogram, Gauge

# Counters
dii_events_ingested_total = Counter(
    'dii_events_ingested_total', 
    'Events entering normalization', 
    ['source_topic']
)

dii_events_validated_total = Counter(
    'dii_events_validated_total', 
    'Events passing validation', 
    ['status']  # accepted, quarantined, duplicate
)

dii_events_enriched_total = Counter(
    'dii_events_enriched_total', 
    'Events successfully enriched', 
    ['status']  # FULL, PARTIAL, NOT_IN_CMDB, NO_IDENTIFIER
)

dii_events_routed_total = Counter(
    'dii_events_routed_total', 
    'Events written to target stores', 
    ['target_store']
)

dii_validation_rejected_total = Counter(
    'dii_validation_rejected_total', 
    'Rejected events by reason', 
    ['reason']
)

# Histograms
dii_validation_latency_seconds = Histogram(
    'dii_validation_latency_seconds', 
    'Validation processing latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

dii_enrichment_latency_seconds = Histogram(
    'dii_enrichment_latency_seconds', 
    'Enrichment lookup latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

dii_e2e_processing_seconds = Histogram(
    'dii_e2e_processing_seconds', 
    'End-to-end processing latency',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Gauges
dii_dlq_messages_total = Gauge(
    'dii_dlq_messages_total', 
    'Unprocessed DLQ messages', 
    ['topic']
)
