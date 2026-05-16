"""Phase 7: Autonomous Behavior via py_trees Behavior Tree.

Tree structure:
  Root (Selector)
  ├── SafetyGuard (battery < 15% → go home)
  ├── HumanEngagement (person detected → interact)
  ├── AutonomousExploration (utility-scored zone selection)
  └── IdlePresence (ambient animations + attentive scan)
"""

import time
import random
from typing import Optional

import py_trees

import config
from pepper.client import PepperClient
from perception.scene import SceneManager
from memory.vault import Vault


class Blackboard:
    """Shared state for the behavior tree."""

    def __init__(self):
        self.battery_level: float = 100.0
        self.person_detected: bool = False
        self.person_id: Optional[str] = None
        self.current_zone: str = "home"
        self.last_scan_time: float = 0
        self.idle_since: float = time.time()
        self.exploration_cooldown: float = 0


# ─── Conditions ──────────────────────────────────────────────────

class BatteryLow(py_trees.behaviour.Behaviour):
    def __init__(self, pepper: PepperClient, threshold: float = 15.0):
        super().__init__(name="BatteryLow?")
        self.pepper = pepper
        self.threshold = threshold

    def update(self):
        battery = self.pepper.battery()
        level = battery.get("level", 100)
        if level < self.threshold:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


class PersonDetected(py_trees.behaviour.Behaviour):
    def __init__(self, scene_mgr: SceneManager):
        super().__init__(name="PersonDetected?")
        self.scene_mgr = scene_mgr

    def update(self):
        scene = self.scene_mgr.current_scene
        if scene and scene.people_count > 0:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


class IdleTimeout(py_trees.behaviour.Behaviour):
    def __init__(self, bb: Blackboard, timeout: float = 120.0):
        super().__init__(name="IdleTimeout?")
        self.bb = bb
        self.timeout = timeout

    def update(self):
        if time.time() - self.bb.idle_since > self.timeout:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE


# ─── Actions ─────────────────────────────────────────────────────

class GoHome(py_trees.behaviour.Behaviour):
    def __init__(self, pepper: PepperClient):
        super().__init__(name="GoHome")
        self.pepper = pepper

    def update(self):
        self.pepper.speak("My battery is low. I need to rest.")
        self.pepper.navigate_to(0.5, 0.5, 0)
        self.pepper.eyes_red()
        return py_trees.common.Status.SUCCESS


class SignalEngagement(py_trees.behaviour.Behaviour):
    """Signal that a person is present — orchestrator handles conversation."""
    def __init__(self, bb: Blackboard):
        super().__init__(name="SignalEngagement")
        self.bb = bb

    def update(self):
        self.bb.person_detected = True
        self.bb.idle_since = time.time()
        return py_trees.common.Status.SUCCESS


class ExploreZone(py_trees.behaviour.Behaviour):
    """Navigate to highest-utility zone and observe."""

    ZONES = [
        {"name": "entrance", "x": 0.5, "y": 5.0, "theta": 3.14},
        {"name": "whiteboard", "x": 3.0, "y": 3.0, "theta": 1.57},
        {"name": "desks", "x": 5.0, "y": 2.0, "theta": 0.0},
        {"name": "coffee", "x": 1.0, "y": 4.0, "theta": 1.0},
        {"name": "window", "x": 6.0, "y": 4.0, "theta": -1.57},
    ]

    def __init__(self, pepper: PepperClient, vault: Vault, bb: Blackboard):
        super().__init__(name="ExploreZone")
        self.pepper = pepper
        self.vault = vault
        self.bb = bb
        self.zone_visits: dict = {z["name"]: 0.0 for z in self.ZONES}

    def update(self):
        if time.time() < self.bb.exploration_cooldown:
            return py_trees.common.Status.FAILURE

        zone = self._pick_zone()
        self.pepper.eyes_blue()
        self.pepper.navigate_to(zone["x"], zone["y"], zone["theta"])
        self.zone_visits[zone["name"]] = time.time()
        self.bb.current_zone = zone["name"]
        self.bb.exploration_cooldown = time.time() + 60
        self.bb.idle_since = time.time()

        self._log_observation(zone["name"])
        return py_trees.common.Status.SUCCESS

    def _pick_zone(self) -> dict:
        """Utility scoring: prefer zones not visited recently."""
        now = time.time()
        scores = []
        for zone in self.ZONES:
            time_since = now - self.zone_visits.get(zone["name"], 0)
            score = min(time_since / 300.0, 1.0) + random.uniform(0, 0.2)
            scores.append((score, zone))
        scores.sort(reverse=True)
        return scores[0][1]

    def _log_observation(self, zone_name: str):
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.vault.append(
            "environment/observations.md",
            f"- [{ts}] Visited {zone_name} (autonomous exploration)"
        )


class IdleAnimation(py_trees.behaviour.Behaviour):
    """Subtle idle animations to appear alive."""

    ANIMATIONS = [
        ("look_left", 0.3),
        ("look_right", 0.3),
        ("look_center", 0.0),
        ("nod_yes", 0.0),
    ]

    def __init__(self, pepper: PepperClient, bb: Blackboard):
        super().__init__(name="IdleAnimation")
        self.pepper = pepper
        self.bb = bb
        self.last_anim_time = 0
        self.cooldown = 8.0

    def update(self):
        now = time.time()
        if now - self.last_anim_time < self.cooldown:
            return py_trees.common.Status.SUCCESS

        anim, arg = random.choice(self.ANIMATIONS)
        method = getattr(self.pepper, anim, None)
        if method:
            if arg:
                method(arg)
            else:
                method()
        self.last_anim_time = now
        self.cooldown = random.uniform(5.0, 15.0)
        return py_trees.common.Status.SUCCESS


# ─── Tree Builder ────────────────────────────────────────────────

def build_tree(pepper: PepperClient, scene_mgr: SceneManager, vault: Vault) -> tuple:
    """Build the autonomous behavior tree. Returns (tree, blackboard)."""
    bb = Blackboard()

    # Safety: low battery → go home
    safety = py_trees.composites.Sequence("Safety", memory=True)
    safety.add_children([BatteryLow(pepper), GoHome(pepper)])

    # Engagement: person detected → signal
    engagement = py_trees.composites.Sequence("Engagement", memory=True)
    engagement.add_children([PersonDetected(scene_mgr), SignalEngagement(bb)])

    # Exploration: idle too long → explore
    exploration = py_trees.composites.Sequence("Exploration", memory=True)
    exploration.add_children([
        IdleTimeout(bb, timeout=120.0),
        ExploreZone(pepper, vault, bb)
    ])

    # Idle: always-on ambient
    idle = IdleAnimation(pepper, bb)

    # Root selector: first success wins
    root = py_trees.composites.Selector("Root", memory=False)
    root.add_children([safety, engagement, exploration, idle])

    tree = py_trees.trees.BehaviourTree(root=root)
    return tree, bb
