"""Kill switch module to safely stop pollers."""
import os
import signal
import threading
import logging
import yaml
from typing import Optional

logger = logging.getLogger(__name__)

class PollerKillSwitch:
    """
    3-tier kill switch for pollers (ADR-0023).
    1. Config flag (hot-reloadable)
    2. Stop file (checked per cycle)
    3. SIGTERM (graceful drain)
    """
    def __init__(self, poller_name: str, config_path: str = "/home/infra/dcim_metrics_project/configs/poller_config.yaml"):
        self.poller_name = poller_name
        self.config_path = config_path
        self.stop_file_path = f"/tmp/dcim_stop_{poller_name}"
        
        self._sigterm_received = False
        self._setup_signal_handlers()
        
    def _setup_signal_handlers(self):
        """Setup SIGTERM handler."""
        original_sigterm = signal.getsignal(signal.SIGTERM)
        
        def _handler(signum, frame):
            logger.info(f"KillSwitch: SIGTERM received for {self.poller_name}. Initiating graceful drain.")
            self._sigterm_received = True
            
            # Call original handler if it exists and is callable
            if callable(original_sigterm):
                original_sigterm(signum, frame)
                
        signal.signal(signal.SIGTERM, _handler)
        
    def _check_config_flag(self) -> bool:
        """Check if poller is explicitly disabled in config."""
        if not os.path.exists(self.config_path):
            return True # Default to enabled if no config
            
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
                
            poller_config = config.get("pollers", {}).get(self.poller_name, {})
            # Return True if enabled is True, or if enabled is not explicitly set to False
            return poller_config.get("enabled", True)
        except Exception as e:
            logger.error(f"KillSwitch: Error reading config {self.config_path}: {e}")
            return True # Fail open
            
    def is_killed(self) -> bool:
        """
        Check all 3 tiers. Returns True if poller should stop.
        """
        # Tier 3: SIGTERM
        if self._sigterm_received:
            return True
            
        # Tier 2: Stop file
        if os.path.exists(self.stop_file_path):
            logger.warning(f"KillSwitch: Stop file detected at {self.stop_file_path}")
            return True
            
        # Tier 1: Config flag
        if not self._check_config_flag():
            logger.warning(f"KillSwitch: Poller disabled in config {self.config_path}")
            return True
            
        return False
        
    def ensure_alive(self):
        """Raise exception if kill switch is engaged. Useful for breaking out of loops."""
        if self.is_killed():
            raise KillSwitchEngagedError(f"Kill switch engaged for {self.poller_name}")

class KillSwitchEngagedError(Exception):
    """Raised when kill switch is engaged."""
    pass
