# Ditch 0.8B Fast Brain — Single 4B + Pre-cached Fillers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the 0.8B fast brain entirely from the architecture. All LLM work goes through the single 4B deep brain. Replace the fast brain's filler/social role with pre-cached audio phrases that play instantly (~10ms) while the 4B generates a real response.

**Architecture:** Two-tier instead of three-brain. Reflex (keyword match) handles instant commands, 4B handles everything else. A `FillerPlayer` pre-renders ~15 filler phrases at startup via edge-tts and plays one immediately when the user starts speaking, buying time for the 4B to generate. The router simplifies to REFLEX vs DEEP (no FAST route). The supervisor simplifies to single-brain circuit breaking.

**Tech Stack:** Python 3.11+, edge-tts (already a dependency), llama.cpp (4B only), existing PepperClient audio API.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| **Create** | `tts/filler.py` | Pre-cache filler audio at startup, play random filler on demand |
| Modify | `config.py` | Remove `FAST_BRAIN_*` settings, add filler config |
| Modify | `core/router.py` | Remove `FAST` route, simplify to REFLEX vs DEEP |
| Modify | `core/orchestrator.py` | Remove fast brain, wire FillerPlayer |
| Modify | `core/supervisor.py` | Remove fast brain, single-brain degradation |
| Modify | `main.py` | Remove fast brain init, add FillerPlayer |
| Modify | `simulator/sim_bridge.py` | Remove fast brain, deep-only + mock fallback |
| Modify | `start_dev.sh` | Remove fast brain, deep-only launch |
| Modify | `start_production.sh` | Remove fast brain, reclaim VRAM for larger context |
| Modify | `brains/llm_client.py` | Remove fast-brain-specific methods (`generate_filler`, `respond_social`) |
| Delete | `pepper_brain/system/fast_brain.md` | No longer needed |

---

### Task 1: Create FillerPlayer

The core new component. Pre-renders filler phrases as WAV bytes at startup using edge-tts. On demand, plays a random one via PepperClient.

**Files:**
- Create: `tts/filler.py`

- [ ] **Step 1: Create `tts/filler.py`**

```python
"""Pre-cached filler audio for instant playback while LLM generates."""

import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pepper.client import PepperClient


FILLER_PHRASES = {
    "en": [
        "Let me think about that.",
        "One moment please.",
        "Good question!",
        "Hmm, let me check.",
        "Sure, give me a second.",
        "Let me look into that.",
        "Interesting question!",
    ],
    "de": [
        "Moment mal, ich denke nach.",
        "Gute Frage!",
        "Einen Augenblick bitte.",
        "Hmm, lass mich nachschauen.",
        "Interessante Frage!",
    ],
}

DEFAULT_VOICE = {
    "en": "en-US-AriaNeural",
    "de": "de-DE-KatjaNeural",
}


class FillerPlayer:
    """Pre-caches filler audio at startup for instant playback."""

    def __init__(self, pepper: PepperClient, languages: list[str] = None):
        self.pepper = pepper
        self._cache: dict[str, list[bytes]] = {}
        languages = languages or ["en"]
        for lang in languages:
            self._cache[lang] = self._render_fillers(lang)

    def play(self, language: str = "en"):
        """Play a random filler. Returns immediately after queueing."""
        clips = self._cache.get(language, self._cache.get("en", []))
        if not clips:
            self.pepper.speak("One moment.", language="en")
            return
        clip = random.choice(clips)
        self.pepper.play_audio(clip)

    def _render_fillers(self, language: str) -> list[bytes]:
        """Pre-render all filler phrases for a language via edge-tts."""
        phrases = FILLER_PHRASES.get(language, FILLER_PHRASES["en"])
        voice = DEFAULT_VOICE.get(language, DEFAULT_VOICE["en"])
        clips = []
        for phrase in phrases:
            wav = self._tts_to_wav(phrase, voice)
            if wav:
                clips.append(wav)
                print(f"[FILLER] Cached: \"{phrase}\" ({len(wav)} bytes)")
            else:
                print(f"[FILLER] WARN: Failed to render \"{phrase}\"")
        print(f"[FILLER] {len(clips)}/{len(phrases)} clips cached for '{language}'")
        return clips

    def _tts_to_wav(self, text: str, voice: str) -> Optional[bytes]:
        """Render one phrase to WAV bytes via edge-tts."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["edge-tts", "--voice", voice, "--text", text,
                 "--write-media", tmp_path],
                capture_output=True, timeout=15,
            )
            if result.returncode != 0:
                return None
            return Path(tmp_path).read_bytes()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
```

- [ ] **Step 2: Verify edge-tts works**

Run: `source .venv/bin/activate && edge-tts --voice en-US-AriaNeural --text "Let me think" --write-media /tmp/test_filler.wav && ls -la /tmp/test_filler.wav`
Expected: WAV file created, non-zero size.

- [ ] **Step 3: Smoke test FillerPlayer import**

Run: `source .venv/bin/activate && python -c "from tts.filler import FillerPlayer, FILLER_PHRASES; print(f'Loaded {sum(len(v) for v in FILLER_PHRASES.values())} phrases')"`
Expected: `Loaded 12 phrases`

- [ ] **Step 4: Commit**

```bash
git add tts/filler.py
git commit -m "add FillerPlayer: pre-cached filler audio for instant playback"
```

---

### Task 2: Simplify Config — Remove Fast Brain

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Remove fast brain config, add filler config**

In `config.py`, remove these lines:
```python
FAST_BRAIN_GGUF = f"{MODEL_DIR}/Qwen3.5-0.8B.Q4_K_M.gguf"
```
```python
FAST_BRAIN_URL = "http://localhost:8091/v1"      # Qwen3.5-0.8B on CPU
```
```python
FAST_BRAIN_MODEL = "qwen3.5-0.8b"
```
```python
FAST_BRAIN_MAX_WORDS = 6
```

Rename `DEEP_BRAIN_*` to just `BRAIN_*` since there's only one now:
```python
# Before
DEEP_BRAIN_GGUF = f"{MODEL_DIR}/Qwen3.5-4B.Q4_K_M.gguf"
DEEP_BRAIN_URL = "http://localhost:8090/v1"
DEEP_BRAIN_MODEL = "qwen3.5-4b"

# After
BRAIN_GGUF = f"{MODEL_DIR}/Qwen3.5-4B.Q4_K_M.gguf"
BRAIN_URL = "http://localhost:8090/v1"
BRAIN_MODEL = "qwen3.5-4b"
```

Add filler config in the TTS section:
```python
# ─── FILLERS ─────────────────────────────────────────────────────
FILLER_LANGUAGES = ["en", "de"]
```

- [ ] **Step 2: Verify config imports**

Run: `source .venv/bin/activate && python -c "import config; print(config.BRAIN_URL); print(config.FILLER_LANGUAGES)"`
Expected:
```
http://localhost:8090/v1
['en', 'de']
```

- [ ] **Step 3: Commit**

```bash
git add config.py
git commit -m "simplify config: remove fast brain, single BRAIN_URL"
```

---

### Task 3: Simplify Router — REFLEX vs DEEP only

The FAST route goes away. Everything that isn't reflex goes to the 4B. No more word-count threshold or escalation.

**Files:**
- Modify: `core/router.py`

- [ ] **Step 1: Replace router.py**

```python
"""Router: decides which brain handles each query.

Routing logic:
  1. REFLEX: keyword match → instant action, no LLM
  2. DEEP (4B): everything else — social, factual, vision, memory
"""

from typing import Optional
from dataclasses import dataclass
from enum import Enum

import config
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
```

- [ ] **Step 2: Verify router**

Run: `source .venv/bin/activate && python -c "from core.router import Router, Route; r = Router(); d = r.route('hello'); print(d.route, d.reason); d2 = r.route('stop'); print(d2.route, d2.reason)"`
Expected:
```
Route.DEEP llm
Route.REFLEX keyword: stop
```

- [ ] **Step 3: Commit**

```bash
git add core/router.py
git commit -m "simplify router: remove FAST route, everything non-reflex goes to 4B"
```

---

### Task 4: Simplify Supervisor — Single Brain

**Files:**
- Modify: `core/supervisor.py`

- [ ] **Step 1: Replace supervisor.py**

```python
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
```

- [ ] **Step 2: Verify supervisor imports**

Run: `source .venv/bin/activate && python -c "from core.supervisor import Supervisor; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/supervisor.py
git commit -m "simplify supervisor: single brain circuit breaker"
```

---

### Task 5: Simplify Orchestrator — Single Brain + FillerPlayer

**Files:**
- Modify: `core/orchestrator.py`

- [ ] **Step 1: Replace orchestrator.py**

```python
"""Orchestrator: main loop wiring perception → router → brain → actions."""

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
```

- [ ] **Step 2: Verify orchestrator imports**

Run: `source .venv/bin/activate && python -c "from core.orchestrator import Orchestrator; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/orchestrator.py
git commit -m "simplify orchestrator: single 4B brain + filler audio"
```

---

### Task 6: Simplify main.py — Single Brain

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update main.py**

Remove all fast brain references. Key changes:

Remove these imports/lines:
```python
# Remove this line from __init__:
self.fast = LLMClient(config.FAST_BRAIN_URL, name="fast", thinking=False)
```

Change `Supervisor(self.deep, self.fast)` → `Supervisor(self.brain)`.

Replace the `__init__` brain setup with:
```python
self.brain = LLMClient(config.BRAIN_URL, name="deep", thinking=True)
self.supervisor = Supervisor(self.brain)
```

Add filler player:
```python
from tts.filler import FillerPlayer
# In __init__:
self.filler = FillerPlayer(self.pepper, config.FILLER_LANGUAGES)
```

In `_process`, remove the `Route.FAST` branch. Replace:
```python
if decision.route == Route.FAST:
    resp = self.supervisor.call_fast(...)
    if resp.escalated:
        ...
else:
    resp = self.supervisor.call_deep(...)
```
With:
```python
# Play filler while brain thinks
filler_thread = threading.Thread(
    target=self.filler.play, args=(self._detect_language(),), daemon=True
)
filler_thread.start()
resp = self.supervisor.call(
    text, system=self._deep_system, profile="social"
)
```

Change `self.supervisor.call_deep(...)` → `self.supervisor.call(...)`.

Add `_detect_language` method (copy from orchestrator).

Update `health_check` print and remove `config.FAST_BRAIN_URL` reference.

- [ ] **Step 2: Full replacement of main.py**

```python
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
from tts.filler import FillerPlayer


class PepperMain:
    """Main application — integrates all systems."""

    def __init__(self):
        print("[MAIN] Initializing Pepper AI...")

        # Clients
        self.pepper = PepperClient(config.BRIDGE_URL)
        self.brain = LLMClient(config.BRAIN_URL, name="deep", thinking=True)

        # Supervisor (circuit breaker)
        self.supervisor = Supervisor(self.brain)

        # Filler audio
        self.filler = FillerPlayer(self.pepper, config.FILLER_LANGUAGES)

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

        # System prompt
        self._system = self.vault.read("system/deep_brain.md") or \
            "You are Pepper, a friendly robot. Keep responses to 2-3 sentences."

        print("[MAIN] Initialization complete.")
        print(f"[MAIN] Health: {self.supervisor.health_check()}")

    def run(self):
        """Main loop: listen + behavior tree tick."""
        self.scene.start()
        self.pepper.eyes_white()
        self.pepper.speak("Hello! I am online and ready.")

        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()

        print("[MAIN] Running. Ctrl+C to stop.")

        while not self._stop.is_set():
            try:
                if self._autonomous and not self.bb.person_detected:
                    self.tree.tick()

                self.pepper.eyes_listening()
                wav = self.pepper.record_audio(seconds=4)
                if wav is None:
                    time.sleep(0.5)
                    continue

                result = self.stt.transcribe_wav_bytes(wav)
                if result is None or not result.text.strip():
                    self.bb.person_detected = False
                    continue

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

        # Play filler while brain thinks
        self.pepper.eyes_thinking()
        filler_thread = threading.Thread(
            target=self.filler.play, args=(self._detect_language(person_id),), daemon=True
        )
        filler_thread.start()

        # Build context
        person_memory = None
        if person_id and self.person_mem.exists(person_id):
            person_memory = self.person_mem.get_quick_context(person_id)

        scene_text = self.scene.scene_text()

        # Call brain via supervisor
        resp = self.supervisor.call(
            text, system=self._system, profile="social"
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
                "deep", resp.completion_tokens,
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

    def _detect_language(self, person_id: str = None) -> str:
        if person_id:
            content = self.person_mem.get(person_id)
            if content:
                import re
                match = re.search(r'^language:\s*(.+)$', content, re.MULTILINE)
                if match:
                    return match.group(1).strip()
        return "en"

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
```

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "simplify main: single 4B brain + filler audio"
```

---

### Task 7: Simplify Start Scripts

**Files:**
- Modify: `start_dev.sh`
- Modify: `start_production.sh`

- [ ] **Step 1: Replace start_dev.sh**

```bash
#!/bin/bash
# Dev mode: single 4B brain on 4GB VRAM
# Thinking ON, reasoning_budget=1024, ctx=8192

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/Qwen3.5-4B.Q4_K_M.gguf"

echo "============================================"
echo "  PEPPER AI — Dev Mode (4GB VRAM)"
echo "  4B: thinking=ON, budget=1024"
echo "============================================"

"$LLAMA_BIN" \
  -m "$MODEL" \
  --host 0.0.0.0 --port 8090 \
  -ngl 24 -np 1 -c 8192 \
  -fa on -ctk q4_0 -ctv q4_0 \
  --swa-full --no-mmap -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024 \
  --threads 8 --threads-batch 16 \
  --spec-type ngram-mod --draft-max 48 --draft-min 0 \
  --spec-ngram-size-n 12 --spec-ngram-size-m 48
```

- [ ] **Step 2: Replace start_production.sh**

```bash
#!/bin/bash
# Production: single 4B brain on 6GB GPU + vision
# Full GPU offload, mmproj enabled, larger context

LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/Qwen3.5-4B.Q4_K_M.gguf"
MMPROJ="$HOME/models/mmproj-F16.gguf"

echo "============================================"
echo "  PEPPER AI — Production Mode (6GB VRAM)"
echo "  4B: thinking=ON + vision"
echo "============================================"

"$LLAMA_BIN" \
  -m "$MODEL" \
  --mmproj "$MMPROJ" \
  --host 0.0.0.0 --port 8090 \
  -ngl 32 -np 1 -c 8192 \
  -fa on -ctk q4_0 -ctv q4_0 \
  --swa-full --no-mmap -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024 \
  --threads 8 --threads-batch 16 \
  --spec-type ngram-mod --draft-max 48 --draft-min 0 \
  --spec-ngram-size-n 12 --spec-ngram-size-m 48
```

- [ ] **Step 3: Commit**

```bash
git add start_dev.sh start_production.sh
git commit -m "simplify start scripts: single 4B brain only"
```

---

### Task 8: Simplify Simulator Bridge

**Files:**
- Modify: `simulator/sim_bridge.py`

- [ ] **Step 1: Update sim_bridge.py LLM section**

Replace the LLM brain initialization (around lines 72-87) with single-brain setup:

Remove:
```python
FAST_BRAIN_URL = os.environ.get("FAST_BRAIN_URL", "http://localhost:8091/v1")
fast_brain = None
```
And the `fast_brain = LLMClient(...)` init.

Replace with:
```python
BRAIN_URL = os.environ.get("BRAIN_URL", "http://localhost:8090/v1")
brain = None
chat_history: list = []

if HAS_LLM:
    brain = LLMClient(base_url=BRAIN_URL, name="deep", thinking=True, default_max_tokens=2048, timeout=90)
    print(f"[LLM] Brain: {BRAIN_URL}")
```

- [ ] **Step 2: Update `_query_llm` method**

Replace with:
```python
def _query_llm(self, text):
    """Try brain → mock fallback."""
    system = "You are Pepper, a friendly humanoid robot. Reply in one or two sentences."
    history = chat_history[:-1] if chat_history else []

    if brain:
        resp = brain.chat(text, system=system, history=history, profile="social", max_tokens=1024)
        if resp.success and resp.spoken_text:
            print(f"[CHAT] Brain: {resp.spoken_text} ({resp.tok_per_sec:.0f} tok/s)")
            return resp.spoken_text, "deep"
        else:
            print(f"[CHAT] Brain failed: success={resp.success} error={resp.error} content={repr(resp.content)}")

    print("[CHAT] Brain unavailable, using mock response")
    mock_responses = [
        "Hello! I'm running in simulator mode right now.",
        "That's an interesting question! Let me think about it.",
        "I'm Pepper, nice to chat with you!",
        "No LLM brain is reachable. Start it with ./start_dev.sh",
    ]
    idx = int(hashlib.md5(text.encode()).hexdigest(), 16) % len(mock_responses)
    return mock_responses[idx], "mock"
```

- [ ] **Step 3: Update `_post_chat` to use `global brain` instead of multiple brains**

The `_post_chat` method doesn't reference brain globals directly (it calls `_query_llm`), so no change needed there.

- [ ] **Step 4: Verify bridge starts**

Run: `source .venv/bin/activate && timeout 3 python -u simulator/sim_bridge.py 2>/dev/null | grep -v ALSA || true`
Expected: Should see `[LLM] Brain: http://localhost:8090/v1` (or connection error if 4B not running).

- [ ] **Step 5: Commit**

```bash
git add simulator/sim_bridge.py
git commit -m "simplify sim_bridge: single brain + mock fallback"
```

---

### Task 9: Clean Up LLM Client

Remove fast-brain-specific convenience methods that are no longer used.

**Files:**
- Modify: `brains/llm_client.py`

- [ ] **Step 1: Remove `generate_filler` and `respond_social` methods**

Delete `generate_filler` (lines ~339-353) and `respond_social` (lines ~355-368) from `LLMClient`. These were designed for the 0.8B fast brain.

Update the module docstring to remove references to "Fast Brain (0.8B)".

- [ ] **Step 2: Update docstring and comments**

Replace:
```python
"""
LLM Client — Dual Brain Interface (v3)
...
Deep Brain (4B): enable_thinking=True → reasoning in `reasoning_content`
Fast Brain (0.8B): enable_thinking=False → direct response, no thinking overhead
"""
```
With:
```python
"""
LLM Client — Brain Interface (v4)
=========================================
Based on official Qwen3.5 documentation + JARVIS audit findings.

Critical: Qwen3.5 requires `chat_template_kwargs: {"enable_thinking": bool}`
passed PER-REQUEST in the API body, not just as a server flag.
"""
```

Remove comments referencing "fast brain" in `TEMP_PROFILES` and `resolve_profile`.

- [ ] **Step 3: Verify client still works**

Run: `source .venv/bin/activate && python -c "from brains.llm_client import LLMClient; c = LLMClient(); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add brains/llm_client.py
git commit -m "clean up llm_client: remove fast-brain methods, update to v4"
```

---

### Task 10: Delete Fast Brain System Prompt

**Files:**
- Delete: `pepper_brain/system/fast_brain.md`

- [ ] **Step 1: Remove the file**

```bash
git rm pepper_brain/system/fast_brain.md
```

- [ ] **Step 2: Commit**

```bash
git commit -m "remove fast_brain.md system prompt"
```

---

### Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update architecture section**

Update the Three-Brain System section to Two-Tier:
```markdown
### Two-Tier System
1. **REFLEX** (~100ms): Keyword matcher for movement commands → direct bridge call
2. **BRAIN** (4B, 18 tok/s on dev): All LLM work — social, factual, vision, memory, web search, tool calls
3. **FILLER** (~10ms): Pre-cached audio phrases play while brain generates
```

Update the services table — remove port 8091 row.

Update the Architecture notes to remove references to 0.8B, fast brain, dual brain.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "update CLAUDE.md: document single-brain architecture"
```

---

### Task 12: End-to-End Smoke Test

- [ ] **Step 1: Start 4B brain**

```bash
./start_dev.sh
```
Wait for `[BRIDGE] Listening on http://localhost:8090`

- [ ] **Step 2: Start simulator bridge**

```bash
cd simulator && source ../.venv/bin/activate && python sim_bridge.py
```

- [ ] **Step 3: Test chat via curl**

```bash
curl -s -X POST http://localhost:5001/chat -H "Content-Type: application/json" -d '{"text": "Hello Pepper!"}' | python -m json.tool
```
Expected: `"routed_to": "deep"` with a real LLM response.

- [ ] **Step 4: Test in browser**

Open http://localhost:5002, send a message in the chat popup.
Expected: Real LLM response, not mock.

- [ ] **Step 5: Verify no references to 8091 remain**

```bash
grep -rn "8091\|fast_brain\|FAST_BRAIN\|0\.8B" --include="*.py" --include="*.sh" --include="*.md" . | grep -v __pycache__ | grep -v node_modules | grep -v plans/
```
Expected: No matches (except maybe in git history or docs/plans).
