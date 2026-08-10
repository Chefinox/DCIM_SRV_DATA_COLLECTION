"""Data quality scorecard engine."""
import time
import logging
import threading
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Gauge
    
    # Prometheus Gauges for Data Quality (6 dimensions)
    dq_completeness = Gauge('dcim_dq_completeness', 'Data Completeness Score (0-1)')
    dq_timeliness = Gauge('dcim_dq_timeliness', 'Data Timeliness Score (0-1)')
    dq_accuracy = Gauge('dcim_dq_accuracy', 'Data Accuracy Score (0-1)')
    dq_consistency = Gauge('dcim_dq_consistency', 'Data Consistency Score (0-1)')
    dq_validity = Gauge('dcim_dq_validity', 'Data Validity Score (0-1)')
    dq_uniqueness = Gauge('dcim_dq_uniqueness', 'Data Uniqueness Score (0-1)')
    dq_overall_score = Gauge('dcim_dq_overall_score', 'Overall Data Quality Score (0-1)')
    has_prometheus = True
except ImportError:
    # Graceful fallback for environments without prometheus_client
    logger.warning("prometheus_client not found. Data quality metrics will not be exported.")
    has_prometheus = False

class DataQualityScorecard:
    """Calculates and exports 6-dimension data quality scores."""
    def __init__(self):
        self._lock = threading.Lock()
        self.reset_counters()
        
    def reset_counters(self):
        with self._lock:
            self.total_events = 0
            
            # Completeness
            self.missing_mandatory_fields = 0
            
            # Timeliness
            self.stale_events = 0
            
            # Accuracy
            self.out_of_range_events = 0
            
            # Consistency
            self.format_invalid_events = 0
            
            # Validity
            self.schema_invalid_events = 0
            
            # Uniqueness
            self.duplicate_events = 0

    def record_validation_result(self, result):
        """Record a validation result from ValidationEngine."""
        with self._lock:
            self.total_events += 1
            
            if result.status == "duplicate":
                self.duplicate_events += 1
                return
                
            for failure in result.failed_rules:
                if "mandatory_field_missing" in failure:
                    self.missing_mandatory_fields += 1
                elif "stale_event" in failure:
                    self.stale_events += 1
                elif "value_out_of_range" in failure:
                    self.out_of_range_events += 1
                elif "format_invalid" in failure:
                    self.format_invalid_events += 1
                elif "schema_invalid" in failure:
                    self.schema_invalid_events += 1

    def calculate_scores(self) -> Dict[str, float]:
        """Calculate current scores (0.0 to 1.0)."""
        with self._lock:
            if self.total_events == 0:
                return {
                    "completeness": 1.0,
                    "timeliness": 1.0,
                    "accuracy": 1.0,
                    "consistency": 1.0,
                    "validity": 1.0,
                    "uniqueness": 1.0,
                    "overall": 1.0
                }
                
            scores = {
                "completeness": max(0.0, 1.0 - (self.missing_mandatory_fields / self.total_events)),
                "timeliness": max(0.0, 1.0 - (self.stale_events / self.total_events)),
                "accuracy": max(0.0, 1.0 - (self.out_of_range_events / self.total_events)),
                "consistency": max(0.0, 1.0 - (self.format_invalid_events / self.total_events)),
                "validity": max(0.0, 1.0 - (self.schema_invalid_events / self.total_events)),
                "uniqueness": max(0.0, 1.0 - (self.duplicate_events / self.total_events))
            }
            
            # Simple average for overall score
            scores["overall"] = sum(scores.values()) / 6.0
            return scores
            
    def export_metrics(self):
        """Export current scores to Prometheus."""
        if not has_prometheus:
            return
            
        scores = self.calculate_scores()
        
        dq_completeness.set(scores["completeness"])
        dq_timeliness.set(scores["timeliness"])
        dq_accuracy.set(scores["accuracy"])
        dq_consistency.set(scores["consistency"])
        dq_validity.set(scores["validity"])
        dq_uniqueness.set(scores["uniqueness"])
        dq_overall_score.set(scores["overall"])
