"""
Unit tests for Circuit Breaker module using standard unittest framework.
Runs state transition checks: CLOSED -> OPEN -> HALF_OPEN -> CLOSED / OPEN.
"""

import time
import unittest
from unittest.mock import patch, MagicMock

from src.utils.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError


@patch("src.utils.circuit_breaker.send_telegram_alert", return_value=True)
class TestCircuitBreaker(unittest.TestCase):

    def test_initial_state_is_closed(self, mock_tg):
        cb = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=10.0)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.allow_request())

    def test_closed_to_open_transition(self, mock_tg):
        cb = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=10.0)

        def failing_func():
            raise ValueError("Service down")

        # Call 1 & 2: Failures under threshold
        with self.assertRaises(ValueError):
            cb.call(failing_func)
        self.assertEqual(cb.state, CircuitState.CLOSED)

        with self.assertRaises(ValueError):
            cb.call(failing_func)
        self.assertEqual(cb.state, CircuitState.CLOSED)

        # Call 3: Reaches threshold (3) -> trips to OPEN
        with self.assertRaises(ValueError):
            cb.call(failing_func)
        self.assertEqual(cb.state, CircuitState.OPEN)

        # Call 4: Fast-fails with CircuitBreakerOpenError without invoking failing_func
        with self.assertRaises(CircuitBreakerOpenError):
            cb.call(failing_func)

    def test_open_to_half_open_recovery(self, mock_tg):
        cb = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=0.2, success_threshold=2)

        def failing_func():
            raise RuntimeError("Fail")

        # Trip to OPEN
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(failing_func)
        self.assertEqual(cb.state, CircuitState.OPEN)

        # Immediately blocked
        with self.assertRaises(CircuitBreakerOpenError):
            cb.call(failing_func)

        # Wait for recovery timeout
        time.sleep(0.25)

        # State transitions to HALF_OPEN on next allow_request check
        self.assertTrue(cb.allow_request())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

    def test_half_open_to_closed_on_success(self, mock_tg):
        cb = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=0.2, success_threshold=2)

        def failing_func():
            raise RuntimeError("Fail")

        def success_func():
            return "OK"

        # Trip to OPEN
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(failing_func)

        time.sleep(0.25)
        self.assertTrue(cb.allow_request())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        # First success in HALF_OPEN
        self.assertEqual(cb.call(success_func), "OK")
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        # Second success -> resets to CLOSED
        self.assertEqual(cb.call(success_func), "OK")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_half_open_to_open_on_failure(self, mock_tg):
        cb = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=0.2, success_threshold=2)

        def failing_func():
            raise RuntimeError("Fail")

        # Trip to OPEN
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cb.call(failing_func)

        time.sleep(0.25)
        self.assertTrue(cb.allow_request())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        # Failure during HALF_OPEN immediately trips back to OPEN
        with self.assertRaises(RuntimeError):
            cb.call(failing_func)
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_telegram_alert_on_trip_and_recovery(self, mock_tg):
        cb = CircuitBreaker("alert_test", failure_threshold=2, recovery_timeout=0.2, success_threshold=1)

        def failing_func():
            raise RuntimeError("Fail")

        def success_func():
            return "OK"

        # Trip
        for _ in range(2):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        self.assertTrue(mock_tg.called)
        self.assertIn("TRIPPED", mock_tg.call_args[0][0])

        mock_tg.reset_mock()
        time.sleep(0.25)

        cb.call(success_func)
        self.assertTrue(mock_tg.called)
        self.assertIn("RECOVERED", mock_tg.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
