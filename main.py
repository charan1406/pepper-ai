#!/usr/bin/env python3
"""Pepper AI — Main Entry Point.

Wires orchestrator + behavior tree + health monitoring.
Run: python main.py
"""

import signal
import sys
import time
import threading

import config
from pepper.client import PepperClient
from brains.llm_client import LLMClient
from core.router import Router, Route
from core.supervisor import Supervisor
from core.health import HealthMonitor
from core.behavior_tree import build_tree, Blackboard
from perception.stt import SpeechToText
from perception.vision import VisionPipeline
from perception.scene import SceneManager
from memory.vault import Vault
from memory.person import PersonMemory


class PepperMain:
    """Main application — integrates all systems."""

    def __init__(self):
        print("[MAIN] Initializing Pepper AI...")

        # Clients
        self.pepper = PepperClient(config.BRIDGE_URL)
        self.deep = LLMClient(config.DEEP_BRAIN_URL, name="deep", thinking=True)
        self.fast = LLMClient(config.FAST_BRAIN_URL, name="fast", thinking=False)

        # Supervisor (circuit breaker)
        self.supervisor = Supervisor(self.deep, self.fast)

        # Perception
        self.stt = SpeechToText()
        self.vision = VisionPipeline()
        self.scene = SceneManager(self.pepper, self.vision)

        # Routing + Memory
        self.router = Router()
        self.vault = Vault()
        self.person_mem = PersonMemory(self.vault)

        # Health
        self.health = HealthMonitor()

        # Behavior tree (autonomous mode)
        self.tree, self.bb = build_tree(self.pepper, self.scene, self.vault)

        # State
        self.history = []
        self._stop = threading.Event()
        self._autonomous = True

        # System prompts
        self._deep_system = self.vault.read("system/deep_brain.md") or \
            "You are Pepper, a friendly robot. Keep responses to 2-3 sentences."

        print("[MAIN] Initialization complete.")
        print(f"[MAIN] Health: {self.supervisor.health_check()}")

    def run(self):
        """Main loop: listen + behavior tree tick."""
        self.scene.start()
        self.pepper.eyes_white()
        self.pepper.speak("Hello! I am online and ready.")

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()

        print("[MAIN] Running. Ctrl+C to stop.")

        while not self._stop.is_set():
            try:
                # Tick behavior tree (handles idle, exploration, safety)
                if self._autonomous and not self.bb.person_detected:
                    self.tree.tick()

                # Listen for speech
                self.pepper.eyes_listening()
                wav = self.pepper.record_audio(seconds=4)
                if wav is None:
                    time.sleep(0.5)
                    continue

                result = self.stt.transcribe_wav_bytes(wav)
                if result is None or not result.text.strip():
                    self.bb.person_detected = False
                    continue

                # Process speech
                self.bb.person_detected = True
                self.bb.idle_since = time.time()
                person_id = self._identify_speaker()

                print(f"[MAIN] Heard: \"{result.text}\" (person: {person_id or 'unknown'})")
                self._process(result.text, person_id)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.health.log_error("main_loop", str(e))
                print(f"[MAIN] Error: {e}")
                time.sleep(1)

        self.shutdown()

    def _process(self, text: str, person_id: str = None):
        """Route and respond to user input."""
        decision = self.router.route(text)

        if decision.route == Route.REFLEX:
            self.router.reflex.execute(decision.reflex_action, self.pepper)
            self.health.log_interaction(text, decision.reflex_action.spoken, "reflex", person_id)
            return

        # Build context
        person_memory = None
        if person_id and self.person_mem.exists(person_id):
            person_memory = self.person_mem.get_quick_context(person_id)

        scene_text = self.scene.scene_text()

        # Call appropriate brain via supervisor
        self.pepper.eyes_thinking()
        if decision.route == Route.FAST:
            resp = self.supervisor.call_fast(
                text, system=self._deep_system, profile="social"
            )
            if resp.escalated:
                self.router.escalate()
                resp = self.supervisor.call_deep(
                    text, system=self._deep_system, profile="social"
                )
        else:
            resp = self.supervisor.call_deep(
                text, system=self._deep_system, profile="social"
            )

        spoken = resp.spoken_text if resp.success and not resp.is_empty else \
            "Sorry, I had a problem thinking."

        # Speak
        self.pepper.eyes_speaking()
        self.pepper.speak(spoken)
        self.pepper.eyes_white()

        # Log
        self.health.log_interaction(text, spoken, decision.route.value, person_id)
        if resp.success:
            self.health.log_llm_call(
                decision.route.value, resp.completion_tokens,
                resp.wall_time, resp.tok_per_sec, True
            )

        # Update memory
        if person_id and self.person_mem.exists(person_id):
            self.person_mem.update_last_seen(person_id)
            self.person_mem.log_conversation(person_id, text, spoken)

        print(f"[MAIN] Said: \"{spoken}\"")

    def _identify_speaker(self):
        scene = self.scene.current_scene
        if not scene or not scene.faces:
            return None
        for face in scene.faces:
            if face.name != "unknown":
                return face.name
        return None

    def _heartbeat_loop(self):
        while not self._stop.is_set():
            self.health.write_heartbeat()
            time.sleep(10)

    def shutdown(self):
        print("\n[MAIN] Shutting down...")
        self._stop.set()
        self.scene.stop()
        self.pepper.eyes_white()
        self.pepper.speak("Goodbye! Shutting down.")
        self.health.close()
        print("[MAIN] Shutdown complete.")


def main():
    app = PepperMain()

    def handle_signal(sig, frame):
        app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    app.run()


if __name__ == "__main__":
    main()
