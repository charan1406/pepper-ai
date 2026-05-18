"""Router: decides which brain handles each query.

Routing logic:
  1. REFLEX: keyword match → instant action, no LLM
  2. DEEP (4B): everything else — social, factual, vision, memory
"""

from typing import Optional
from dataclasses import dataclass
from enum import Enum

from brains.reflex import ReflexBrain, ReflexAction


class Route(Enum):
    REFLEX = "reflex"
    DEEP = "deep"


@dataclass
class RoutingDecision:
    route: Route
    reason: str
    reflex_action: Optional[ReflexAction] = None


class Router:
    def __init__(self):
        self.reflex = ReflexBrain()

    def route(self, text: str, has_image: bool = False) -> RoutingDecision:
        """Decide which brain handles this input."""
        action = self.reflex.match(text)
        if action:
            return RoutingDecision(Route.REFLEX, f"keyword: {action.command}", action)

        return RoutingDecision(Route.DEEP, "llm")
