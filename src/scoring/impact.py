"""Impact scoring engine for the DCIM pipeline."""
import os
import yaml
from typing import Dict, Any, Optional

CONFIG_PATH = os.environ.get("IMPACT_CONFIG_PATH", "/home/infra/dcim_metrics_project/configs/impact_scoring.yaml")

class ImpactScorer:
    """Calculates impact score = criticality × severity."""
    def __init__(self):
        self._load_config()

    def _load_config(self):
        self.criticality_weights = {
            "critical": 5,
            "high": 4,
            "medium": 3,
            "low": 2,
            "minimal": 1
        }
        
        self.severity_weights = {
            "critical": 5,
            "error": 4,
            "warning": 3,
            "info": 1
        }
        
        self.thresholds = {
            "P1": 15,
            "P2": 6,
            "P3": 1
        }
        
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    if "criticality_weights" in config:
                        self.criticality_weights = config["criticality_weights"]
                    if "severity_weights" in config:
                        self.severity_weights = config["severity_weights"]
                    if "impact_thresholds" in config:
                        self.thresholds = config["impact_thresholds"]
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to load impact config: {e}")

    def calculate(self, criticality: str, severity: str) -> Dict[str, Any]:
        """
        Calculate impact score and priority.
        criticality: e.g., 'high', 'medium' (from CMDB)
        severity: e.g., 'warning', 'critical' (from Poller/Event)
        """
        c_weight = self.criticality_weights.get(str(criticality).lower(), 1)
        s_weight = self.severity_weights.get(str(severity).lower(), 1)
        
        score = c_weight * s_weight
        
        priority = "P3"
        if score >= self.thresholds.get("P1", 15):
            priority = "P1"
        elif score >= self.thresholds.get("P2", 6):
            priority = "P2"
            
        return {
            "impact_score": score,
            "impact_priority": priority,
            "criticality_weight": c_weight,
            "severity_weight": s_weight
        }
