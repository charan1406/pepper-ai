"""Orchestrator: main loop wiring perception → router → brains → actions."""

import threading
import time
from typing import Optional, List
from dataclasses import dataclass

import config
from pepper.client import PepperClient
from brains.llm_client import LLMClient, LLMResponse, Message
from brains.reflex import ReflexBrain
from core.router import Router, Route, RoutingDecision
from perception.stt import SpeechToText, TranscriptResult
from perception.vision import VisionPipeline
from perception.scene import SceneManager
from memory.vault import Vault
from memory.person import PersonMemory


SYSTEM_PROMPT_PATH = "system/deep_brain.md"
FAST_PROMPT_PATH = "system/fast_brain.md"


@dataclass
class Turn:
    user_text: str
    response_text: str
    route: Route
    person_id: Optional[str] = None


class Orchestrator:
    """Main control loop: listen → route → think → speak → remember."""

    def __init__(self,
                 bridge_url: str = config.BRIDGE_URL,
                 deep_url: str = config.DEEP_BRAIN_URL,
                 fast_url: str = config.FAST_BRAIN_URL):
        # Clients
        self.pepper = PepperClient(bridge_url)
        self.deep = LLMClient(deep_url, name="deep", thinking=True)
        self.fast = LLMClient(fast_url, name="fast", thinking=True)

        # Perception
        self.stt = SpeechToText()
        self.vision = VisionPipeline()
        self.scene = SceneManager(self.pepper, self.vision)

        # Routing
        self.router = Router()

        # Memory
        self.vault = Vault()
        self.person_mem = PersonMemory(self.vault)

        # State
        self.history: List[Message] = []
        self.current_person: Optional[str] = None
        self._stop = threading.Event()

        # Load system prompts
        self._deep_system = self.vault.read(SYSTEM_PROMPT_PATH) or ""
        self._fast_system = self.vault.read(FAST_PROMPT_PATH) or ""

    def start(self):
        """Start perception and enter main loop."""
        self.scene.start()
        self.pepper.eyes_white()
        print("[ORCH] Orchestrator started. Listening...")
        self._listen_loop()

    def stop(self):
        self._stop.set()
        self.scene.stop()

    def process_text(self, text: str, person_id: Optional[str] = None) -> str:
        """Process a text input and return the spoken response. Main entry point."""
        self.current_person = person_id

        # Route
        decision = self.router.route(text, has_image=False)

        # Execute based on route
        if decision.route == Route.REFLEX:
            self.router.reflex.execute(decision.reflex_action, self.pepper)
            return decision.reflex_action.spoken

        elif decision.route == Route.FAST:
            response = self._fast_respond(text)
            if response.escalated:
                self.router.escalate()
                response = self._deep_respond(text)
        else:
            response = self._deep_respond(text)

        # Get spoken text
        spoken = response.spoken_text if response.success else "Sorry, I had a problem thinking."

        # Update history
        self.history.append(Message("user", text))
        self.history.append(Message("assistant", spoken))
        if len(self.history) > config.MAX_CONVERSATION_HISTORY * 2:
            self.history = self.history[-config.MAX_CONVERSATION_HISTORY * 2:]

        # Speak
        self.pepper.eyes_speaking()
        self.pepper.speak(spoken)
        self.pepper.eyes_white()

        # Update person memory
        if person_id and self.person_mem.exists(person_id):
            self.person_mem.update_last_seen(person_id)
            self.person_mem.log_conversation(person_id, text, spoken)

        return spoken

    def _fast_respond(self, text: str) -> LLMResponse:
        self.pepper.eyes_thinking()
        person_name = self._get_person_name()
        return self.fast.respond_social(
            text, person_name=person_name,
            language=self._detect_language()
        )

    def _deep_respond(self, text: str) -> LLMResponse:
        self.pepper.eyes_thinking()
        person_memory = None
        if self.current_person:
            person_memory = self.person_mem.get_quick_context(self.current_person)

        scene_text = self.scene.scene_text()
        system = self._deep_system or "You are Pepper, a friendly robot. Keep responses to 2-3 sentences."

        return self.deep.deep_query(
            user_message=text,
            system=system,
            person_memory=person_memory,
            scene=scene_text,
            history=self.history[-config.MAX_CONVERSATION_HISTORY:],
            profile="social",
        )

    def _listen_loop(self):
        """Continuous listen → process loop."""
        while not self._stop.is_set():
            self.pepper.eyes_listening()
            wav = self.pepper.record_audio(seconds=5)
            if wav is None:
                time.sleep(0.5)
                continue

            result = self.stt.transcribe_wav_bytes(wav)
            if result is None or not result.text.strip():
                continue

            # Identify person from scene
            person_id = self._identify_speaker()

            print(f"[ORCH] Heard: \"{result.text}\" (person: {person_id or 'unknown'})")
            response = self.process_text(result.text, person_id=person_id)
            print(f"[ORCH] Said: \"{response}\"")

    def _identify_speaker(self) -> Optional[str]:
        """Try to identify the current speaker from scene faces."""
        scene = self.scene.current_scene
        if not scene or not scene.faces:
            return None
        for face in scene.faces:
            if face.name != "unknown":
                return face.name
        return None

    def _get_person_name(self) -> Optional[str]:
        if not self.current_person:
            return None
        content = self.person_mem.get(self.current_person)
        if content:
            import re
            match = re.search(r'^name:\s*(.+)$', content, re.MULTILINE)
            if match:
                return match.group(1).strip()
        return self.current_person.replace("_", " ").title()

    def _detect_language(self) -> str:
        """Simple language detection from current person's profile."""
        if self.current_person:
            content = self.person_mem.get(self.current_person)
            if content:
                import re
                match = re.search(r'^language:\s*(.+)$', content, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        return "en"
