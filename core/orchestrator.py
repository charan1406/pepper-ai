"""Orchestrator: main loop wiring perception -> router -> brain -> actions."""

import json
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
from tools.web_search import WebSearch
from brains.llm_client import resolve_profile


SYSTEM_PROMPT_PATH = "system/deep_brain.md"
MAX_TOOL_ROUNDS = 3


@dataclass
class Turn:
    user_text: str
    response_text: str
    route: Route
    person_id: Optional[str] = None


class Orchestrator:
    """Main control loop: listen -> route -> think -> speak -> remember."""

    def __init__(self,
                 bridge_url: str = config.BRIDGE_URL,
                 brain_url: str = config.BRAIN_URL):
        self.pepper = PepperClient(bridge_url)
        self.brain = LLMClient(brain_url, name="deep", thinking=True)

        self.filler = FillerPlayer(self.pepper, config.FILLER_LANGUAGES)

        self.stt = SpeechToText()
        self.vision = VisionPipeline()
        self.scene = SceneManager(self.pepper, self.vision)

        self.router = Router()

        self.vault = Vault()
        self.person_mem = PersonMemory(self.vault)
        self.search = WebSearch()

        self.history: List[Message] = []
        self.current_person: Optional[str] = None
        self._stop = threading.Event()

        self._system = self.vault.read(SYSTEM_PROMPT_PATH) or ""
        self._tools = [self.search.tool_definition()]

    def start(self):
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

        decision = self.router.route(text, has_image=False)

        if decision.route == Route.REFLEX:
            self.router.reflex.execute(decision.reflex_action, self.pepper)
            return decision.reflex_action.spoken

        language = self._detect_language()
        self.pepper.eyes_thinking()
        filler_thread = threading.Thread(
            target=self.filler.play, args=(language,), daemon=True
        )
        filler_thread.start()

        response = self._respond_with_tools(text)

        spoken = response.spoken_text if response.success else "Sorry, I had a problem thinking."

        self.history.append(Message("user", text))
        self.history.append(Message("assistant", spoken))
        if len(self.history) > config.MAX_CONVERSATION_HISTORY * 2:
            self.history = self.history[-config.MAX_CONVERSATION_HISTORY * 2:]

        self.pepper.eyes_speaking()
        self.pepper.speak(spoken)
        self.pepper.eyes_white()

        if person_id and self.person_mem.exists(person_id):
            self.person_mem.update_last_seen(person_id)
            self.person_mem.log_conversation(person_id, text, spoken)

        return spoken

    def _respond_with_tools(self, text: str) -> LLMResponse:
        """Query brain with agentic tool loop (max 3 rounds for 4B)."""
        person_memory = None
        if self.current_person:
            person_memory = self.person_mem.get_quick_context(self.current_person)

        scene_text = self.scene.scene_text()
        system = self._system or "You are Pepper, a friendly robot. Keep responses to 2-3 sentences."

        messages = self._build_messages(system, text, person_memory, scene_text)
        response = LLMResponse(success=False, error="no tool rounds configured")

        for round_num in range(MAX_TOOL_ROUNDS):
            response = self.brain._call(
                messages,
                max_tokens=self.brain.default_max_tokens,
                tools=self._tools,
                **resolve_profile("social", self.brain.thinking),
            )

            if not response.success:
                return response

            if not response.has_tool_calls:
                return response

            messages.append({
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": [
                    {
                        "id": f"call_{round_num}_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"] if isinstance(tc["arguments"], str) else json.dumps(tc["arguments"]),
                        },
                    }
                    for i, tc in enumerate(response.tool_calls)
                ],
            })

            for i, tc in enumerate(response.tool_calls):
                result = self._execute_tool(tc)
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{round_num}_{i}",
                    "content": result,
                })

            print(f"[ORCH] Tool round {round_num + 1}: {[tc['name'] for tc in response.tool_calls]}")

        return response

    def _build_messages(self, system: str, text: str,
                        person_memory: Optional[str],
                        scene_text: Optional[str]) -> list:
        """Build the message array with token budgets and observation masking."""
        system_trimmed = _trim_to_budget(system, config.TOKEN_BUDGET_SYSTEM_PROMPT)
        messages = [{"role": "system", "content": system_trimmed}]

        masked = self._mask_history(self.history[-config.MAX_CONVERSATION_HISTORY:])
        history_text = ""
        for msg in masked:
            entry = msg.to_dict()
            history_text += entry.get("content", "")
            if _estimate_tokens(history_text) > config.TOKEN_BUDGET_CONVERSATION:
                break
            messages.append(entry)

        parts = []
        if scene_text:
            parts.append(f"[SCENE]\n{_trim_to_budget(scene_text, config.TOKEN_BUDGET_SCENE)}")
        if person_memory:
            parts.append(f"[PERSON MEMORY]\n{_trim_to_budget(person_memory, config.TOKEN_BUDGET_PERSON_MEMORY)}")
        parts.append(f"[USER]\n{text}")

        messages.append({"role": "user", "content": "\n\n".join(parts)})
        return messages

    def _mask_history(self, history: List[Message]) -> List[Message]:
        """Observation masking per JetBrains/TUM 'Complexity Trap' paper.

        Keep the last 10 turns (20 messages) fully intact.
        Older assistant messages get truncated to save context.
        """
        KEEP_RECENT = 20
        if len(history) <= KEEP_RECENT:
            return list(history)

        masked = []
        cutoff = len(history) - KEEP_RECENT
        for i, msg in enumerate(history):
            if i < cutoff and msg.role == "assistant" and len(msg.content) > 150:
                masked.append(Message(msg.role, msg.content[:80] + " [earlier response truncated]"))
            else:
                masked.append(msg)
        return masked

    def _execute_tool(self, tool_call: dict) -> str:
        """Execute a tool call and return the result as text."""
        name = tool_call.get("name", "")
        args = tool_call.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return f"Error: invalid arguments JSON for {name}"

        if name == "web_search":
            query = args.get("query", "")
            if not query:
                return "Error: missing query parameter"
            results = self.search.search(query)
            formatted = self.search.format_for_llm(results)
            print(f"[ORCH] web_search('{query}') -> {len(results)} results")
            return formatted

        return f"Unknown tool: {name}"

    def _listen_loop(self):
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

    def _detect_language(self) -> str:
        if self.current_person:
            content = self.person_mem.get(self.current_person)
            if content:
                import re
                match = re.search(r'^language:\s*(.+)$', content, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        return "en"


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _trim_to_budget(text: str, token_budget: int) -> str:
    char_budget = token_budget * 4
    if len(text) <= char_budget:
        return text
    return text[:char_budget - 3] + "..."
