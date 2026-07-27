"""
Circuit Breaker Pattern Module for DCIM Pipeline Services.
Ref: dcim-wiki block9 §2.2 & block2 §9.5
"""

import time
import logging
import threading
from enum import Enum
import requests
import json
import os

from src.observability.logging.dcim_logger import setup_logger

logger = setup_logger("circuit_breaker", "/home/infra/dcim_metrics_project/logs/circuit_breaker.log")

# Telegram Alerter Integration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8320149476:AAFy2G5ma1YQnQeIC-PBuwFH1xxiKO38JF4")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5266403936")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def send_telegram_alert(message: str) -> bool:
    """Send alert message to Telegram group."""
    try:
        resp = requests.post(TELEGRAM_API, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=5)
        return resp.ok
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


class CircuitState(Enum):
    CLOSED = "closed"        # Normal state: requests pass through
    OPEN = "open"            # Tripped state: requests fail-fast / DLQ routed
    HALF_OPEN = "half_open"  # Recovery testing: allow trial requests


class CircuitBreakerOpenError(Exception):
    """Exception raised when a call is attempted on an OPEN CircuitBreaker."""
    pass


class CircuitBreaker:
    """
    Circuit Breaker state machine for managing external service calls.
    
    Attributes:
        name (str): Service identifier (e.g. 'itop', 'redis', 'elasticsearch')
        failure_threshold (int): Number of consecutive failures before tripping to OPEN
        recovery_timeout (float): Time in seconds to wait in OPEN state before trying HALF_OPEN
        success_threshold (int): Consecutive successes in HALF_OPEN required to reset to CLOSED
    """
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.last_state_change = time.time()
        
        self._lock = threading.Lock()

    def _set_state(self, new_state: CircuitState):
        old_state = self.state
        if old_state != new_state:
            self.state = new_state
            self.last_state_change = time.time()
            log_msg = f"[CIRCUIT BREAKER] Service '{self.name}' state changed: {old_state.value.upper()} -> {new_state.value.upper()}"
            logger.warning(log_msg)
            
            # Send Telegram Alert
            if new_state == CircuitState.OPEN:
                tg_msg = (
                    f"⚠️ <b>[DCIM CIRCUIT BREAKER TRIPPED]</b>\n\n"
                    f"<b>Service:</b> <code>{self.name}</code>\n"
                    f"<b>Status:</b> OPEN 🔴\n"
                    f"<b>Failures:</b> {self.failure_count}/{self.failure_threshold}\n"
                    f"<b>Recovery Timeout:</b> {self.recovery_timeout}s\n"
                    f"<b>Action:</b> Requests automatically routed to DLQ"
                )
                send_telegram_alert(tg_msg)
            elif new_state == CircuitState.CLOSED and old_state != CircuitState.CLOSED:
                tg_msg = (
                    f"✅ <b>[DCIM CIRCUIT BREAKER RECOVERED]</b>\n\n"
                    f"<b>Service:</b> <code>{self.name}</code>\n"
                    f"<b>Status:</b> CLOSED 🟢\n"
                    f"<b>Action:</b> Normal processing resumed"
                )
                send_telegram_alert(tg_msg)

    def _should_attempt_reset(self) -> bool:
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def allow_request(self) -> bool:
        """Check if request is allowed based on current circuit state."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._set_state(CircuitState.HALF_OPEN)
                    self.success_count = 0
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

            return False

    def on_success(self):
        """Callback on successful call execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.failure_count = 0
                    self.success_count = 0
                    self._set_state(CircuitState.CLOSED)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def on_failure(self, error: Exception = None):
        """Callback on failed call execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                logger.error(f"[CIRCUIT BREAKER] Service '{self.name}' failed during HALF_OPEN trial: {error}")
                self._set_state(CircuitState.OPEN)
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    logger.error(f"[CIRCUIT BREAKER] Service '{self.name}' failure threshold ({self.failure_threshold}) reached: {error}")
                    self._set_state(CircuitState.OPEN)

    def call(self, func, *args, **kwargs):
        """
        Execute function wrapped with circuit breaker protection.
        Raises CircuitBreakerOpenError if state is OPEN and timeout hasn't elapsed.
        """
        if not self.allow_request():
            raise CircuitBreakerOpenError(f"Circuit breaker is OPEN for service '{self.name}'")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure(e)
            raise
