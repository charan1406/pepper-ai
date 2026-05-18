"""Orchestrator: main loop wiring perception → router → brain → actions."""

import threading
import time
from typing import Optional, List
from dataclasses import dataclass

import config
from pepper.client import PepperClient
from brains.llm_client import LLMClient, LLMResponse, Message
from core.router import Router, Route
from perception.stt import SpeechToText
from perception.vision import VisionPipeline
from perception.scene import SceneManager
from memory.vault import Vault
from memory.person import PersonMemory
from tts.filler import FillerPlayer


SYSTEM_PROMPT_PATH = "system/deep_brain.md"


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
                 brain_url: str = config.BRAIN_URL):
        # Clients
        self.pepper = PepperClient(bridge_url)
        self.brain = LLMClient(brain_url, name="deep", thinking=True)

        # Filler audio
        self.filler = FillerPlayer(self.pepper, config.FILLER_LANGUAGES)

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

        # Load system prompt
        self._system = self.vault.read(SYSTEM_PROMPT_PATH) or ""

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
        """Process a text input and return the spoken response."""
        self.current_person = person_id

        # Route
        decision = self.router.route(text, has_image=False)

        # Reflex — instant, no LLM
        if decision.route == Route.REFLEX:
            self.router.reflex.execute(decision.reflex_action, self.pepper)
            return decision.reflex_action.spoken

        # Play filler while 4B thinks
        language = self._detect_language()
        self.pepper.eyes_thinking()
        filler_thread = threading.Thread(
            target=self.filler.play, args=(language,), daemon=True
        )
        filler_thread.start()

        # Get real response from 4B
        response = self._respond(text)

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

    def _respond(self, text: str) -> LLMResponse:
        person_memory = None
        if self.current_person:
            person_memory = self.person_mem.get_quick_context(self.current_person)

        scene_text = self.scene.scene_text()
        system = self._system or "You are Pepper, a friendly robot. Keep responses to 2-3 sentences."

        return self.brain.deep_query(
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

            person_id = self._identify_speaker()

            print(f"[ORCH] Heard: \"{result.text}\" (person: {person_id or 'unknown'})")
            response = self.process_text(result.text, person_id=person_id)
            print(f"[ORCH] Said: \"{response}\"")

    def _identify_speaker(self) -> Optional[str]:
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
        if self.current_person:
            content = self.person_mem.get(self.current_person)
            if content:
                import re
                match = re.search(r'^language:\s*(.+)$', content, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        return "en"
