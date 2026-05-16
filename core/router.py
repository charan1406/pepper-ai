"""Router: decides which brain handles each query.

Routing logic:
  1. REFLEX: keyword match → instant action, no LLM
  2. FAST (0.8B): short greetings, fillers, social (<= FAST_BRAIN_MAX_WORDS)
  3. DEEP (4B): factual queries, tool use, vision, memory, long input

The fast brain can ESCALATE to deep if it can't handle something.
Deep momentum: once deep brain activates, it stays for N turns.
"""

from typing import Optional
from dataclasses import dataclass
from enum import Enum

import config
from brains.reflex import ReflexBrain, ReflexAction


class Route(Enum):
    REFLEX = "reflex"
    FAST = "fast"
    DEEP = "deep"


@dataclass
class RoutingDecision:
    route: Route
    reason: str
    reflex_action: Optional[ReflexAction] = None


class Router:
    def __init__(self):
        self.reflex = ReflexBrain()
        self.deep_momentum = 0
        self.max_words_fast = config.FAST_BRAIN_MAX_WORDS
        self.momentum_turns = config.DEEP_MOMENTUM_TURNS

        self._deep_triggers = [
            "explain", "why", "how does", "what is", "tell me about",
            "search", "look up", "find", "remember", "recall",
            "what do you see", "look at", "describe",
            "translate", "summarize", "compare",
        ]

    def route(self, text: str, has_image: bool = False) -> RoutingDecision:
        """Decide which brain handles this input."""
        # 1. Reflex check
        action = self.reflex.match(text)
        if action:
            self.deep_momentum = 0
            return RoutingDecision(Route.REFLEX, f"keyword: {action.command}", action)

        # 2. Deep momentum — stay on deep brain for continuity
        if self.deep_momentum > 0:
            self.deep_momentum -= 1
            return RoutingDecision(Route.DEEP, f"momentum ({self.deep_momentum + 1} left)")

        # 3. Vision always goes deep
        if has_image:
            self._activate_deep()
            return RoutingDecision(Route.DEEP, "has image input")

        # 4. Check deep triggers
        text_lower = text.lower()
        for trigger in self._deep_triggers:
            if trigger in text_lower:
                self._activate_deep()
                return RoutingDecision(Route.DEEP, f"trigger: {trigger}")

        # 5. Long input goes deep
        word_count = len(text.split())
        if word_count > self.max_words_fast:
            self._activate_deep()
            return RoutingDecision(Route.DEEP, f"long input ({word_count} words)")

        # 6. Default: fast brain
        return RoutingDecision(Route.FAST, "short/social input")

    def escalate(self):
        """Called when fast brain returns ESCALATE."""
        self._activate_deep()

    def _activate_deep(self):
        self.deep_momentum = self.momentum_turns
