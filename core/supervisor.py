"""Production Hardening — Circuit Breaker + Graceful Degradation.

Degradation ladder:
  Level 0: Full capability (deep + reflex)
  Level 1: Brain offline → reflex + canned responses
  Level 2: Bridge offline → log everything, wait for reconnect
"""

import time
from typing import Dict
from dataclasses import dataclass
from collections import defaultdict

from brains.llm_client import LLMClient, LLMResponse


@dataclass
class CircuitState:
    failure_count: int = 0
    last_failure: float = 0
    is_open: bool = False
    half_open_at: float = 0


class CircuitBreaker:
    """Circuit breaker — prevents cascading failures."""

    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 30.0):
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.circuits: Dict[str, CircuitState] = defaultdict(CircuitState)

    def can_call(self, brain_name: str) -> bool:
        state = self.circuits[brain_name]
        if not state.is_open:
            return True
        if time.time() >= state.half_open_at:
            return True
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

    def __init__(self, brain: LLMClient):
        self.brain = brain
        self.breaker = CircuitBreaker()
        self._canned_idx = 0

    @property
    def degradation_level(self) -> int:
        if self.breaker.can_call("brain"):
            return 0
        return 1

    def call(self, *args, **kwargs) -> LLMResponse:
        if not self.breaker.can_call("brain"):
            return self._fallback()
        resp = self.brain.chat(*args, **kwargs)
        if resp.success:
            self.breaker.record_success("brain")
        else:
            self.breaker.record_failure("brain")
        return resp

    def _fallback(self) -> LLMResponse:
        text = CANNED_RESPONSES[self._canned_idx % len(CANNED_RESPONSES)]
        self._canned_idx += 1
        return LLMResponse(
            content=text,
            success=True,
            error="circuit open for brain",
        )

    def health_check(self) -> Dict:
        return {
            "brain_alive": self.brain.is_alive(),
            "circuits": self.breaker.status(),
            "degradation_level": self.degradation_level,
        }
