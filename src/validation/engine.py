"""Validation engine for normalized events."""
import time
from typing import Dict, List, Any, Optional

class ValidationResult:
    def __init__(self, status: str = "accepted", reason: str = None):
        self.status = status  # "accepted", "quarantined", "duplicate"
        self.failed_rules: List[str] = []
        self.quality_flags: List[str] = []
        if reason:
            self.failed_rules.append(reason)

    @property
    def is_accepted(self) -> bool:
        return self.status == "accepted"


class ValidationRule:
    """Base class for validation rules."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)

    def validate(self, event: Dict[str, Any], result: ValidationResult) -> None:
        """Override to implement rule logic. Modify result object inline."""
        pass


class ValidationEngine:
    """Orchestrates validation rules against normalized events."""
    def __init__(self, config: Dict[str, Any], dry_run: bool = True):
        self.config = config
        self.dry_run = dry_run
        self.rules: List[ValidationRule] = []
        self._initialize_rules()
        
        # Initialize Deduplication
        from .dedup import DeduplicationChecker
        self.dedup_checker = DeduplicationChecker(config.get("deduplication", {}))

    def _initialize_rules(self):
        from .rules import RangeRule, FormatRule, FreshnessRule, SourceAllowlistRule
        
        rule_mapping = {
            "range": RangeRule,
            "format": FormatRule,
            "freshness": FreshnessRule,
            "source_allowlist": SourceAllowlistRule
        }
        
        for rule_name, rule_class in rule_mapping.items():
            rule_config = self.config.get(rule_name, {})
            if rule_config.get("enabled", True):
                self.rules.append(rule_class(rule_config))

    def validate(self, event: Dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        
        # 1. Check deduplication first (fastest)
        if self.dedup_checker.enabled:
            if self.dedup_checker.is_duplicate(event):
                result.status = "duplicate"
                result.failed_rules.append("duplicate: content hash matches recent event")
                
                if not self.dry_run:
                    return result
        
        # 2. Run rule chain
        for rule in self.rules:
            if not rule.enabled:
                continue
            rule.validate(event, result)
            
            # Fast-fail if not in dry_run mode and status is already quarantined
            if not self.dry_run and result.status not in ("accepted", "duplicate"):
                break
                
        # If in dry-run mode, we always accept the event, but we attach the quality flags / failure reasons
        if self.dry_run and result.status != "accepted":
            # Add a flag to indicate it would have failed
            result.quality_flags.append(f"dry_run_failure: {','.join(result.failed_rules)}")
            result.status = "accepted"
            result.failed_rules = []
            
        return result
