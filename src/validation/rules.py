from typing import Dict, Any, List

class BaseRule:
    def validate(self, event: Dict[str, Any]) -> bool:
        raise NotImplementedError

class RangeRule(BaseRule):
    def __init__(self, limits: Dict[str, Dict[str, float]]):
        self.limits = limits

    def validate(self, event: Dict[str, Any]) -> bool:
        metrics = event.get('metrics', {})
        for metric, bounds in self.limits.items():
            if metric in metrics:
                val = metrics[metric]
                if val < bounds.get('min', float('-inf')) or val > bounds.get('max', float('inf')):
                    return False
        return True

class FormatRule(BaseRule):
    def validate(self, event: Dict[str, Any]) -> bool:
        # Check basic schema format
        required_fields = ['hostname', 'metrics', 'timestamp']
        for field in required_fields:
            if field not in event:
                return False
        return True

class FreshnessRule(BaseRule):
    def __init__(self, max_age_seconds: int = 300):
        self.max_age_seconds = max_age_seconds
        
    def validate(self, event: Dict[str, Any]) -> bool:
        import time
        from datetime import datetime
        
        event_time_str = event.get('timestamp')
        if not event_time_str:
            return False
            
        try:
            # Assuming ISO format with Z or timezone
            # Removing Z for simplified parsing
            if event_time_str.endswith('Z'):
                event_time_str = event_time_str[:-1]
                
            event_time = datetime.fromisoformat(event_time_str).timestamp()
            current_time = time.time()
            
            if (current_time - event_time) > self.max_age_seconds:
                return False
                
        except ValueError:
            pass # Invalid timestamp format handled softly
            
        return True

class SourceAllowlistRule(BaseRule):
    def __init__(self, allowlist: List[str]):
        self.allowlist = allowlist
        
    def validate(self, event: Dict[str, Any]) -> bool:
        hostname = event.get('hostname', '')
        # If allowlist is empty, pass all, otherwise check
        if not self.allowlist:
            return True
            
        return any(hostname.startswith(allowed) or allowed == hostname for allowed in self.allowlist)
