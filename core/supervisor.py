"""Phase 8: Production Hardening — Circuit Breaker + Graceful Degradation.

Degradation ladder:
  Level 0: Full capability (deep + fast + reflex)
  Level 1: Deep brain offline → fast brain handles all
  Level 2: Both brains offline → reflex + canned responses
  Level 3: Bridge offline → log everything, wait for reconnect
"""

import time
import json
from typing import Optional, Dict
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

from brains.llm_client import LLMClient, LLMResponse


@dataclass
class CircuitState:
    failure_count: int = 0
    last_failure: float = 0
    is_open: bool = False
    half_open_at: float = 0


class CircuitBreaker:
    """Circuit breaker per brain — prevents cascading failures."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0):
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.circuits: Dict[str, CircuitState] = defaultdict(CircuitState)

    def can_call(self, brain_name: str) -> bool:
        state = self.circuits[brain_name]
        if not state.is_open:
            return True
        if time.time() >= state.half_open_at:
            return True  # half-open probe
        return False

    def record_success(self, brain_name: str):
        state = self.circuits[brain_name]
        state.failure_count = 0
        state.is_open = False

    def record_failure(self, brain_name: str):
        state = self.circuits[brain_name]
        state.failure_count += 1
        state.last_failure = time.time()
        if state.failure_count >= self.threshold:
            state.is_open = True
            state.half_open_at = time.time() + self.reset_timeout

    def status(self) -> Dict[str, str]:
        return {
            name: "OPEN" if s.is_open else "CLOSED"
            for name, s in self.circuits.items()
        }


CANNED_RESPONSES = [
    "I'm having trouble thinking right now, but I'm still here!",
    "Let me get back to you on that — my brain needs a moment.",
    "I can still help with basic things. Try asking me to move or look around!",
]


class Supervisor:
    """Manages brain health, degradation, and fallback responses."""

    def __init__(self, deep: LLMClient, fast: LLMClient):
        self.deep = deep
        self.fast = fast
        self.breaker = CircuitBreaker()
        self._canned_idx = 0

    @property
    def degradation_level(self) -> int:
        deep_ok = self.breaker.can_call("deep")
        fast_ok = self.breaker.can_call("fast")
        if deep_ok and fast_ok:
            return 0
        elif fast_ok:
            return 1
        elif deep_ok:
            return 1
        else:
            return 2

    def call_deep(self, *args, **kwargs) -> LLMResponse:
        if not self.breaker.can_call("deep"):
            return self._fallback("deep")
        resp = self.deep.chat(*args, **kwargs)
        if resp.success:
            self.breaker.record_success("deep")
        else:
            self.breaker.record_failure("deep")
        return resp

    def call_fast(self, *args, **kwargs) -> LLMResponse:
        if not self.breaker.can_call("fast"):
            return self._fallback("fast")
        resp = self.fast.chat(*args, **kwargs)
        if resp.success:
            self.breaker.record_success("fast")
        else:
            self.breaker.record_failure("fast")
        return resp

    def _fallback(self, brain_name: str) -> LLMResponse:
        text = CANNED_RESPONSES[self._canned_idx % len(CANNED_RESPONSES)]
        self._canned_idx += 1
        return LLMResponse(
            content=text,
            success=True,
            error=f"circuit open for {brain_name}",
        )

    def health_check(self) -> Dict:
        return {
            "deep_alive": self.deep.is_alive(),
            "fast_alive": self.fast.is_alive(),
            "circuits": self.breaker.status(),
            "degradation_level": self.degradation_level,
        }
