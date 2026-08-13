from typing import Dict, Any, List
from .rules import BaseRule, FormatRule, RangeRule, FreshnessRule, SourceAllowlistRule
from .config import load_config

class ValidationEngine:
    def __init__(self, config_path: str = "configs/validation_rules.yaml"):
        self.rules: List[BaseRule] = []
        self._load_rules(config_path)
        
    def _load_rules(self, config_path: str):
        config = load_config(config_path)
        
        # Always add format rule
        self.rules.append(FormatRule())
        
        # Add range rule if defined
        if 'ranges' in config:
            self.rules.append(RangeRule(config['ranges']))
            
        # Add freshness rule if defined
        freshness_config = config.get('freshness', {})
        max_age = freshness_config.get('max_age_seconds', 300)
        self.rules.append(FreshnessRule(max_age))
        
        # Add source allowlist if defined
        allowlist = config.get('allowlist', [])
        if allowlist:
            self.rules.append(SourceAllowlistRule(allowlist))

    def validate(self, event: Dict[str, Any]) -> bool:
        for rule in self.rules:
            if not rule.validate(event):
                return False
        return True
