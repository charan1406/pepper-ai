"""Reflex Brain: keyword-matched instant commands (~100ms)"""

from typing import Optional, Tuple
from dataclasses import dataclass

import config


@dataclass
class ReflexAction:
    command: str       # "forward", "stop", "sit", etc.
    action_fn: str     # method name on PepperClient
    args: dict         # kwargs for the method
    spoken: str        # what Pepper says while doing it


# Maps command keys to (pepper_client_method, kwargs, spoken_response)
ACTION_MAP = {
    "stop":    ("stop_moving", {},                "Stopping."),
    "forward": ("move_to",    {"x": 1.0},        "Moving forward."),
    "back":    ("move_to",    {"x": -0.5},       "Going back."),
    "left":    ("move_to",    {"theta": 1.57},   "Turning left."),
    "right":   ("move_to",    {"theta": -1.57},  "Turning right."),
    "sit":     ("set_posture", {"posture": "Crouch"}, "Sitting down."),
    "stand":   ("set_posture", {"posture": "Stand"},  "Standing up."),
    "dance":   ("run_animation", {"name": "animations/Stand/Gestures/Hey_1"}, "Let me dance!"),
    "quiet":   ("stop_speaking", {},              ""),
}


class ReflexBrain:
    """Instant keyword matching for movement commands."""

    def __init__(self):
        self.commands = config.REFLEX_COMMANDS

    def match(self, text: str) -> Optional[ReflexAction]:
        """Check if text matches a reflex command. Returns action or None."""
        text_lower = text.lower().strip()

        for cmd_key, lang_map in self.commands.items():
            for lang, keywords in lang_map.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        if cmd_key in ACTION_MAP:
                            method, args, spoken = ACTION_MAP[cmd_key]
                            return ReflexAction(
                                command=cmd_key,
                                action_fn=method,
                                args=args,
                                spoken=spoken,
                            )
        return None

    def execute(self, action: ReflexAction, pepper_client) -> bool:
        """Execute a reflex action on the pepper client."""
        method = getattr(pepper_client, action.action_fn, None)
        if method is None:
            return False
        method(**action.args)
        if action.spoken:
            pepper_client.speak(action.spoken)
        return True
