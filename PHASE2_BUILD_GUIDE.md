# Pepper AI — Phase 2 Build Guide
## Perception: Whisper STT + YOLO + Face Recognition
### For the next session — build perfectly on first try

---

## PROJECT CONTEXT (read this first)

This is a Pepper robot AI system.
Development environment: 4GB VRAM RTX 3050 laptop (dev), 6GB VRAM machine (production with real Pepper 1.8 robot).

### What's already built (Phase 1 — DONE):
- `pepper/client.py` — HTTP client for simulator bridge (all endpoints)
- `brains/llm_client.py` — Dual brain LLM client (4B deep + 0.8B fast, Qwen3.5)
- `simulator/sim_bridge.py` — Mock Pepper bridge with 3D web frontend
- `simulator/sim_state.py` — Physics engine with smooth movement
- `simulator/web/` — React + Three.js 3D Pepper model in a lab room
- `pepper/bridge.py` — Real NAOqi bridge (Python 2.7, untested)
- `pepper_brain/` — Obsidian vault with system prompts, person templates, backlinks
- `config.py` — Central config, model paths, all settings
- `test_phase1.py` — Working test suite + interactive chat
- `start_dev.sh` — Launches both brains on shared 4GB VRAM
- `chat.html` — Browser chat interface for testing brains
- `.venv/` — Python venv at project root

### Key files to understand:
- `config.py` has all ports, paths, thresholds
- `pepper/client.py` has `get_camera_frame()`, `record_audio()`, `get_audio_chunk()`
- `brains/llm_client.py` has `LLMClient`, `LLMResponse`, `Message`
- Bridge runs on `localhost:5001`, deep brain on `:8090`, fast brain on `:8091`
- llama-server binary: built from llama.cpp (see README for setup)
- Models: `~/models/` or set `PEPPER_MODEL_DIR` (Qwen3.5-4B, 0.8B, mmproj)
- Arch Linux, uses kitty terminal, zsh, venv required (PEP 668)

### Qwen3.5 specifics (CRITICAL):
- Small models NEED thinking enabled for quality output
- Pass `chat_template_kwargs: {"enable_thinking": true}` PER-REQUEST in API body
- Official sampling: temp=1.0, top_p=0.95, top_k=20, presence_penalty=1.5
- Never use temperature=0.0 (causes infinite loops)
- reasoning_content field contains thinking, content field has the response
- `spoken_text` property on LLMResponse cleans leaked reasoning from small models

---

## PHASE 2 OVERVIEW

Build 3 modules that give Pepper ears and eyes:

```
perception/
├── stt.py              # Speech-to-text (Whisper + VAD)
├── vision.py           # Object detection (YOLOv8n) + face recognition
└── scene.py            # Maintains current scene state dict
```

---

## MODULE 1: perception/stt.py

### Purpose
Capture audio from Pepper's microphone (via bridge), detect when someone
is speaking (VAD), buffer their speech, and transcribe it with Whisper.

### Dependencies (install in .venv)
```bash
pip install faster-whisper silero-vad numpy
# faster-whisper uses CTranslate2, runs on CPU, ~500MB RAM for 'small' model
# silero-vad is a tiny (~1MB) neural VAD model
```

### Architecture
```
Bridge /audio/stream → raw 16-bit 16kHz mono chunks
         │
         ▼
  Ring Buffer (always filling, last 30s of audio)
         │
         ▼
  Silero VAD (runs on every chunk, ~1ms per check)
    │           │
    │ silence   │ speech detected
    │           ▼
    │     Speech Buffer (accumulating)
    │           │
    │     silence > 700ms after speech
    │           │
    │           ▼
    │     faster-whisper transcribe
    │           │
    │           ▼
    │     TranscriptResult(text, language, confidence)
    │
    (continue listening)
```

### Key Design Decisions
1. **Use bridge `/audio/record` for simplicity** — don't stream.
   The bridge records N seconds and returns WAV bytes.
   For dev: record 5s chunks, transcribe, repeat.
   Streaming can be added later.

2. **Whisper model size**: `small` (244M params, ~500MB RAM)
   - `base` is faster but less accurate
   - `medium` is better but 1.5GB RAM
   - `small` is the sweet spot for CPU

3. **Language detection**: faster-whisper auto-detects language.
   Returns `info.language` ("en", "de", "ta", etc.)

4. **VAD (Voice Activity Detection)**: Silero VAD
   - Tiny model, runs in real-time on CPU
   - Prevents transcribing silence/noise
   - Threshold: 0.5 probability
   - Min speech duration: 250ms
   - Silence timeout: 700ms

### Implementation Skeleton
```python
"""perception/stt.py"""

import io
import wave
import base64
import numpy as np
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass

from faster_whisper import WhisperModel

@dataclass
class TranscriptResult:
    text: str
    language: str
    confidence: float
    duration: float  # seconds of audio

class SpeechToText:
    def __init__(self,
                 model_size: str = "small",
                 device: str = "cpu",
                 compute_type: str = "int8",
                 vad_threshold: float = 0.5,
                 silence_timeout: float = 0.7,
                 min_speech_duration: float = 0.25):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.vad_threshold = vad_threshold
        self.silence_timeout = silence_timeout
        self.min_speech_duration = min_speech_duration
        # Load Silero VAD
        import torch
        self.vad_model, self.vad_utils = torch.hub.load(
            'snakers4/silero-vad', 'silero_vad', trust_repo=True
        )
        self.get_speech_timestamps = self.vad_utils[0]
    
    def transcribe_wav_bytes(self, wav_b64: str) -> Optional[TranscriptResult]:
        """Transcribe base64 WAV audio from the bridge."""
        wav_bytes = base64.b64decode(wav_b64)
        # Parse WAV to numpy float32 array
        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Check VAD — is there speech in this audio?
        import torch
        audio_tensor = torch.from_numpy(audio)
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor, self.vad_model,
            threshold=self.vad_threshold,
            min_speech_duration_ms=int(self.min_speech_duration * 1000),
            sampling_rate=16000
        )
        if not speech_timestamps:
            return None  # No speech detected
        
        # Transcribe with faster-whisper
        segments, info = self.model.transcribe(audio, language=None)  # auto-detect
        text = " ".join(seg.text for seg in segments).strip()
        
        if not text:
            return None
        
        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=info.language_probability,
            duration=len(audio) / 16000
        )
    
    def listen_loop(self, pepper_client, callback: Callable[[TranscriptResult], None],
                    record_seconds: float = 5.0, stop_event: threading.Event = None):
        """Continuous listening loop — records chunks and transcribes."""
        while not (stop_event and stop_event.is_set()):
            # Record audio from Pepper mic
            wav_b64 = pepper_client.record_audio(seconds=record_seconds)
            if wav_b64 is None:
                time.sleep(0.5)
                continue
            
            result = self.transcribe_wav_bytes(wav_b64)
            if result and result.text.strip():
                callback(result)
```

### Testing Strategy
```python
# In test_phase2.py:
from pepper.client import PepperClient
from perception.stt import SpeechToText

pepper = PepperClient("http://localhost:5001")
stt = SpeechToText(model_size="small")

# Record 5 seconds from Pepper mic (laptop mic in simulator)
wav = pepper.record_audio(seconds=5)
result = stt.transcribe_wav_bytes(wav)
print(f"Heard: {result.text} (language: {result.language})")
```

### Edge Cases
- Pepper's motors make noise → mic gating (don't record while Pepper speaks)
- Background lab noise → VAD filters most of it
- Very short utterances ("yes", "no") → min_speech_duration catches these
- Whisper hallucination on silence → VAD prevents this

---

## MODULE 2: perception/vision.py

### Purpose
Grab camera frames from Pepper, run YOLOv8n for object detection,
run face_recognition for person identification.

### Dependencies
```bash
pip install ultralytics opencv-python face-recognition numpy
# ultralytics: YOLOv8 (auto-downloads yolov8n.pt, ~6MB)
# face-recognition: dlib-based face detection + encoding
# On Arch: may need `sudo pacman -S cmake` for dlib compilation
```

### Architecture
```
Bridge /camera/frame → base64 JPEG → decode to numpy array
         │
    ┌────┴────┐
    ▼         ▼
  YOLOv8n   face_recognition
  (CPU)      (CPU)
    │         │
    ▼         ▼
  objects[]  faces[]
    │         │
    └────┬────┘
         ▼
  SceneUpdate(objects, faces, timestamp)
```

### Implementation Skeleton
```python
"""perception/vision.py"""

import base64
import numpy as np
import cv2
import time
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pathlib import Path

@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)

@dataclass
class DetectedFace:
    name: str          # "john_smith" or "unknown_001"
    confidence: float  # face distance (lower = better match)
    bbox: tuple        # (top, right, bottom, left)
    encoding: Optional[np.ndarray] = None

@dataclass 
class SceneUpdate:
    objects: List[DetectedObject] = field(default_factory=list)
    faces: List[DetectedFace] = field(default_factory=list)
    people_count: int = 0
    timestamp: float = 0

class VisionPipeline:
    def __init__(self,
                 yolo_model: str = "yolov8n.pt",
                 yolo_confidence: float = 0.5,
                 face_tolerance: float = 0.6,
                 face_model: str = "hog",
                 encodings_dir: str = "pepper_brain/encodings"):
        # YOLO
        from ultralytics import YOLO
        self.yolo = YOLO(yolo_model)
        self.yolo_confidence = yolo_confidence
        
        # Face recognition
        import face_recognition as fr
        self.fr = fr
        self.face_tolerance = face_tolerance
        self.face_model = face_model
        
        # Load known face encodings
        self.known_encodings = {}  # name → encoding array
        self.encodings_dir = Path(encodings_dir)
        self._load_known_faces()
    
    def _load_known_faces(self):
        """Load saved face encodings from .npy files."""
        if not self.encodings_dir.exists():
            return
        for npy_file in self.encodings_dir.glob("*.npy"):
            name = npy_file.stem  # e.g. "john_smith"
            self.known_encodings[name] = np.load(npy_file)
    
    def _decode_frame(self, b64_jpeg: str) -> np.ndarray:
        """Decode base64 JPEG to OpenCV numpy array."""
        jpeg_bytes = base64.b64decode(b64_jpeg)
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    
    def detect_objects(self, frame: np.ndarray) -> List[DetectedObject]:
        """Run YOLOv8n on a frame."""
        results = self.yolo(frame, conf=self.yolo_confidence, verbose=False)
        objects = []
        for r in results:
            for box in r.boxes:
                label = self.yolo.names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                objects.append(DetectedObject(label, conf, (x1, y1, x2, y2)))
        return objects
    
    def detect_faces(self, frame: np.ndarray) -> List[DetectedFace]:
        """Detect and identify faces in a frame."""
        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Find faces
        locations = self.fr.face_locations(rgb, model=self.face_model)
        encodings = self.fr.face_encodings(rgb, locations)
        
        faces = []
        for (top, right, bottom, left), encoding in zip(locations, encodings):
            # Compare against known faces
            name = "unknown"
            best_distance = 1.0
            
            for known_name, known_enc in self.known_encodings.items():
                distance = self.fr.face_distance([known_enc], encoding)[0]
                if distance < best_distance and distance < self.face_tolerance:
                    best_distance = distance
                    name = known_name
            
            faces.append(DetectedFace(
                name=name,
                confidence=1.0 - best_distance,
                bbox=(top, right, bottom, left),
                encoding=encoding
            ))
        
        return faces
    
    def process_frame(self, b64_jpeg: str) -> SceneUpdate:
        """Full pipeline: decode → YOLO + face → SceneUpdate."""
        frame = self._decode_frame(b64_jpeg)
        
        objects = self.detect_objects(frame)
        faces = self.detect_faces(frame)
        people_count = sum(1 for o in objects if o.label == "person")
        
        return SceneUpdate(
            objects=objects,
            faces=faces,
            people_count=people_count,
            timestamp=time.time()
        )
    
    def enroll_face(self, name: str, b64_frames: List[str]) -> bool:
        """Enroll a new person from multiple camera frames."""
        all_encodings = []
        for b64 in b64_frames:
            frame = self._decode_frame(b64)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            encodings = self.fr.face_encodings(rgb)
            if encodings:
                all_encodings.append(encodings[0])
        
        if not all_encodings:
            return False
        
        # Average encoding for robustness
        avg_encoding = np.mean(all_encodings, axis=0)
        
        # Save
        self.encodings_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.encodings_dir / f"{name}.npy", avg_encoding)
        self.known_encodings[name] = avg_encoding
        
        return True
```

### Testing Strategy
```python
# In test_phase2.py:
from pepper.client import PepperClient
from perception.vision import VisionPipeline

pepper = PepperClient("http://localhost:5001")
vision = VisionPipeline()

# Get a frame
frame_b64 = pepper.get_camera_frame()
scene = vision.process_frame(frame_b64)

print(f"Objects: {[o.label for o in scene.objects]}")
print(f"Faces: {[f.name for f in scene.faces]}")
print(f"People: {scene.people_count}")
```

### Dlib Compilation on Arch Linux
face_recognition depends on dlib which needs to compile:
```bash
sudo pacman -S cmake
pip install dlib face-recognition  # this takes ~5 minutes to compile
```
If dlib fails, alternative: use `face-recognition` with `model="hog"` (no GPU needed).

---

## MODULE 3: perception/scene.py

### Purpose
Maintains a real-time scene description dict that's always current.
Background thread runs YOLO continuously, face_recognition periodically.
The orchestrator reads this dict whenever building an LLM prompt.

### Implementation Skeleton
```python
"""perception/scene.py"""

import threading
import time
from typing import Optional, Dict
from perception.vision import VisionPipeline, SceneUpdate

class SceneManager:
    """Maintains current scene state, updated by background threads."""
    
    def __init__(self, pepper_client, vision: VisionPipeline,
                 yolo_interval: float = 1.0,
                 face_interval: float = 3.0):
        self.pepper = pepper_client
        self.vision = vision
        self.yolo_interval = yolo_interval
        self.face_interval = face_interval
        
        self._current_scene: Optional[SceneUpdate] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
    
    @property
    def current_scene(self) -> Optional[SceneUpdate]:
        with self._lock:
            return self._current_scene
    
    def scene_text(self) -> str:
        """Format scene as text for LLM prompt injection."""
        scene = self.current_scene
        if not scene:
            return "No scene data available."
        
        parts = []
        if scene.people_count > 0:
            parts.append(f"People detected: {scene.people_count}")
        
        if scene.faces:
            names = [f.name for f in scene.faces]
            parts.append(f"Identified: {', '.join(names)}")
        
        if scene.objects:
            labels = list(set(o.label for o in scene.objects if o.label != "person"))
            if labels:
                parts.append(f"Objects: {', '.join(labels)}")
        
        return " | ".join(parts) if parts else "Room appears empty."
    
    def start(self):
        """Start background vision threads."""
        self._stop.clear()
        t = threading.Thread(target=self._vision_loop, daemon=True)
        t.start()
    
    def stop(self):
        self._stop.set()
    
    def _vision_loop(self):
        """Background loop: grab frames, run detection."""
        last_face_time = 0
        while not self._stop.is_set():
            try:
                frame_b64 = self.pepper.get_camera_frame()
                if frame_b64:
                    scene = self.vision.process_frame(frame_b64)
                    with self._lock:
                        self._current_scene = scene
            except Exception as e:
                print(f"[VISION] Error: {e}")
            
            time.sleep(self.yolo_interval)
```

---

## TEST FILE: test_phase2.py

```python
#!/usr/bin/env python3
"""Phase 2 Test — Perception Pipeline"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pepper.client import PepperClient
from perception.stt import SpeechToText
from perception.vision import VisionPipeline
from perception.scene import SceneManager

BRIDGE = "http://localhost:5001"

def test_stt():
    print("── TEST: Speech-to-Text ──")
    pepper = PepperClient(BRIDGE)
    stt = SpeechToText(model_size="small")
    
    print("  Recording 5 seconds... speak now!")
    wav = pepper.record_audio(seconds=5)
    if wav:
        result = stt.transcribe_wav_bytes(wav)
        if result:
            print(f"  ✓ Heard: \"{result.text}\"")
            print(f"    Language: {result.language} ({result.confidence:.0%})")
        else:
            print("  ✗ No speech detected (silence or noise)")
    else:
        print("  ✗ No audio from bridge")

def test_vision():
    print("\n── TEST: Vision Pipeline ──")
    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()
    
    frame = pepper.get_camera_frame()
    if frame:
        scene = vision.process_frame(frame)
        print(f"  ✓ Objects: {[o.label for o in scene.objects]}")
        print(f"  ✓ Faces: {[f'{f.name} ({f.confidence:.0%})' for f in scene.faces]}")
        print(f"  ✓ People count: {scene.people_count}")
    else:
        print("  ✗ No frame from bridge")

def test_scene():
    print("\n── TEST: Scene Manager ──")
    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()
    scene_mgr = SceneManager(pepper, vision)
    
    scene_mgr.start()
    print("  Running scene manager for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        text = scene_mgr.scene_text()
        print(f"  [{i+1}s] {text}")
    scene_mgr.stop()
    print("  ✓ Scene manager test complete")

if __name__ == "__main__":
    test_stt()
    test_vision()
    test_scene()
```

---

## INSTALL SCRIPT

```bash
#!/bin/bash
# Phase 2 dependencies
cd ~/Projects/pepper-ai
source .venv/bin/activate

pip install faster-whisper numpy
pip install ultralytics opencv-python

# face_recognition needs cmake + dlib
sudo pacman -S cmake --needed
pip install dlib face-recognition

# Silero VAD (downloads via torch hub on first use)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

echo "Phase 2 dependencies installed"
```

---

## WHAT COMES AFTER PHASE 2

Phase 3: Router + Reflex (core/router.py, brains/reflex.py)
Phase 4: Memory (memory/vault.py, memory/person.py)
Phase 5: Orchestrator (core/orchestrator.py — wires everything)
Phase 6: Web search + TTS + Tablet
Phase 7: Autonomous exploration mode
Phase 8: Production hardening

The router and orchestrator are where all the model quality issues get
properly handled — routing simple queries to fast brain, complex to deep,
cleaning outputs, managing conversation state, mic gating during speech, etc.
