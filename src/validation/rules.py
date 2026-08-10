"""Implementation of specific validation rules."""
import time
import re
from typing import Dict, Any
from .engine import ValidationRule, ValidationResult

class RangeRule(ValidationRule):
    def validate(self, event: Dict[str, Any], result: ValidationResult) -> None:
        metric_name = event.get("metric_name")
        if not metric_name:
            return
            
        metric_configs = self.config.get("metrics", {})
        if metric_name not in metric_configs:
            return
            
        bounds = metric_configs[metric_name]
        try:
            value = float(event.get("metric_value", 0))
            if "min" in bounds and value < bounds["min"]:
                result.status = "quarantined"
                result.failed_rules.append(f"value_out_of_range: {value} < {bounds['min']}")
            elif "max" in bounds and value > bounds["max"]:
                result.status = "quarantined"
                result.failed_rules.append(f"value_out_of_range: {value} > {bounds['max']}")
            else:
                # Check for near_range_boundary quality flag
                if "min" in bounds and "max" in bounds:
                    span = bounds["max"] - bounds["min"]
                    if span > 0:
                        pct = (value - bounds["min"]) / span
                        if pct < 0.1 or pct > 0.9:
                            result.quality_flags.append("near_range_boundary")
        except (ValueError, TypeError):
            result.status = "quarantined"
            result.failed_rules.append("type_mismatch: value not numeric")


class FormatRule(ValidationRule):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.compiled_patterns = {}
        for field, props in self.config.get("fields", {}).items():
            pattern = props.get("pattern")
            if pattern:
                try:
                    self.compiled_patterns[field] = re.compile(pattern)
                except re.error:
                    pass

    def validate(self, event: Dict[str, Any], result: ValidationResult) -> None:
        raw_fields = event.get("raw_fields", {})
        if not isinstance(raw_fields, dict):
            return
            
        for field, pattern in self.compiled_patterns.items():
            if field in raw_fields:
                val = str(raw_fields[field])
                if not pattern.match(val):
                    result.status = "quarantined"
                    result.failed_rules.append(f"format_invalid: {field}")


class FreshnessRule(ValidationRule):
    def validate(self, event: Dict[str, Any], result: ValidationResult) -> None:
        max_staleness = self.config.get("max_staleness_seconds", 300)
        
        # Try to get event time, fallback to ingestion time
        event_time_ms = event.get("event_time") or event.get("timestamp")
        if not event_time_ms:
            return
            
        try:
            # Convert ms to s if needed
            if event_time_ms > 2000000000000:
                event_time_s = event_time_ms / 1000.0
            else:
                event_time_s = event_time_ms
                
            now_s = time.time()
            diff = now_s - event_time_s
            
            if diff > max_staleness:
                result.status = "quarantined"
                result.failed_rules.append(f"stale_event: {diff:.1f}s > {max_staleness}s")
            elif diff > 60:
                result.quality_flags.append("clock_skew_detected")
                
        except (ValueError, TypeError):
            pass


class SourceAllowlistRule(ValidationRule):
    def validate(self, event: Dict[str, Any], result: ValidationResult) -> None:
        allowed = self.config.get("allowed_topics", [])
        if not allowed:
            return
            
        topic = event.get("source_topic")
        if not topic:
            return
            
        # Match topic prefix
        is_allowed = False
        for allowed_prefix in allowed:
            if topic.startswith(allowed_prefix):
                is_allowed = True
                break
                
        if not is_allowed:
            result.status = "quarantined"
            result.failed_rules.append(f"source_rejected: {topic}")
