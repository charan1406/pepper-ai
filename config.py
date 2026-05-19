"""
Pepper AI — Central Configuration
===================================
Override any setting via environment variables or a config.local.py file.
Change BRIDGE_URL to swap between simulator and real Pepper.
"""

import os
from pathlib import Path

# ─── BRIDGE CONNECTION ───────────────────────────────────────────
BRIDGE_URL = os.getenv("PEPPER_BRIDGE_URL", "http://localhost:5001")

# Real Pepper IP (only used by pepper/bridge.py, not by middleware)
PEPPER_IP = os.getenv("PEPPER_IP", "192.168.1.100")
PEPPER_PORT = int(os.getenv("PEPPER_PORT", "9559"))

# ─── MODEL PATHS ──────────────────────────────────────────────────
MODEL_DIR = os.getenv("PEPPER_MODEL_DIR", str(Path.home() / "models"))
BRAIN_GGUF = f"{MODEL_DIR}/Qwen3.5-4B.Q4_K_M.gguf"
MMPROJ_GGUF = f"{MODEL_DIR}/mmproj-F16.gguf"

# ─── LLM SERVERS ─────────────────────────────────────────────────
BRAIN_URL = "http://localhost:8090/v1"
BRAIN_MODEL = "qwen3.5-4b"

# ─── VRAM BUDGET ──────────────────────────────────────────────────
# 4GB laptop testing: text-only, no mmproj, 4K context
# 6GB production: mmproj enabled, 8K context
ENABLE_MMPROJ = False        # Set True on 6GB+ GPU
CONTEXT_SIZE = 8192          # Fits on 4GB with q4_0 KV cache + partial offload

# ─── TTS ENGINE ──────────────────────────────────────────────────
# "kokoro-gpu" on 6GB prod (real-time, offline), "kokoro-cpu" on dev, "edge" as fallback
KOKORO_GPU = os.getenv("PEPPER_KOKORO_GPU", "false").lower() == "true"
KOKORO_MODEL_ONNX = f"{MODEL_DIR}/kokoro-v1.0.int8.onnx"
KOKORO_VOICES_BIN = f"{MODEL_DIR}/voices-v1.0.bin"

# ─── PERCEPTION ───────────────────────────────────────────────────
# Dev: "small" (244M). Prod: "distil-large-v3" (5.8x faster than large, ~1% WER gap)
WHISPER_MODEL = os.getenv("PEPPER_WHISPER_MODEL", "small")
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

YOLO_MODEL = "yolo26n.pt"
YOLO_CONFIDENCE = 0.5

FACE_RECOGNITION_TOLERANCE = 0.4   # Cosine similarity threshold for InsightFace
FACE_RECOGNITION_MODEL = "buffalo_sc"  # InsightFace model pack (lightweight)
FACE_RECOGNITION_BACKEND = "insightface"  # "insightface" or "dlib" (legacy)

# ─── AUDIO ────────────────────────────────────────────────────────
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
VAD_THRESHOLD = 0.5
SILENCE_TIMEOUT_MS = 700
MIN_SPEECH_DURATION_MS = 250
MAX_RECORDING_DURATION_S = 30

# ─── TTS ──────────────────────────────────────────────────────────
PEPPER_NATIVE_TTS_LANGUAGES = [
    "en", "de", "fr", "it", "es", "ja", "zh", "ar",
    "pt", "ko", "nl", "pl", "cs", "tr", "sv", "da", "no", "fi"
]
PIPER_TTS_ENABLED = True
EDGE_TTS_ENABLED = True       # Fallback, needs internet
EDGE_TTS_VOICE_TAMIL = "ta-IN-PallaviNeural"
EDGE_TTS_VOICE_DEFAULT = "en-US-AriaNeural"

# ─── FILLERS ─────────────────────────────────────────────────────
FILLER_LANGUAGES = ["en", "de"]

# ─── MEMORY / OBSIDIAN BRAIN ─────────────────────────────────────
BRAIN_VAULT_PATH = "./pepper_brain"
MAX_QUICK_CONTEXT_ITEMS = 10
MAX_CONVERSATION_HISTORY = 20
MEMORY_CONSOLIDATION_THRESHOLD = 10
WEB_CACHE_TTL_SECONDS = 3600  # 1 hour
SEARX_URL = os.getenv("SEARX_URL", "http://localhost:8080/search")

# ─── CONTEXT WINDOW BUDGET (tokens) ──────────────────────────────
TOKEN_BUDGET_SYSTEM_PROMPT = 400
TOKEN_BUDGET_RULES = 200
TOKEN_BUDGET_TOOLS = 300
TOKEN_BUDGET_SCENE = 50
TOKEN_BUDGET_PERSON_MEMORY = 350
TOKEN_BUDGET_CONVERSATION = 2000
TOKEN_BUDGET_SEARCH_RESULTS = 1500
TOKEN_BUDGET_LLM_OUTPUT = 500

# ─── TEMPERATURE PROFILES ────────────────────────────────────────
TEMP_FACTUAL = {"temperature": 0.1, "top_p": 0.9}
TEMP_MEMORY = {"temperature": 0.1, "top_p": 0.9}
TEMP_TOOL_CALL = {"temperature": 0.0, "top_p": 1.0}
TEMP_VISION = {"temperature": 0.3, "top_p": 0.9}
TEMP_SOCIAL = {"temperature": 0.7, "top_p": 0.95}
TEMP_CREATIVE = {"temperature": 0.9, "top_p": 0.95}

# ─── ROUTER THRESHOLDS ───────────────────────────────────────────
DEEP_MOMENTUM_TURNS = 2
ESCALATE_KEYWORD = "ESCALATE"

# ─── MULTILINGUAL REFLEX KEYWORDS ────────────────────────────────
REFLEX_COMMANDS = {
    "stop":     {"en": ["stop"], "de": ["stopp", "halt"], "ta": ["நிறுத்து"]},
    "forward":  {"en": ["go forward", "move forward"], "de": ["vorwärts"], "ta": ["முன்னே போ"]},
    "back":     {"en": ["go back", "move back"], "de": ["zurück"], "ta": ["பின்னே போ"]},
    "left":     {"en": ["turn left"], "de": ["links"], "ta": ["இடது"]},
    "right":    {"en": ["turn right"], "de": ["rechts"], "ta": ["வலது"]},
    "sit":      {"en": ["sit down"], "de": ["hinsetzen"], "ta": ["உட்கார்"]},
    "stand":    {"en": ["stand up"], "de": ["aufstehen"], "ta": ["எழுந்திரு"]},
    "dance":    {"en": ["dance"], "de": ["tanz"], "ta": ["நடனம்"]},
    "quiet":    {"en": ["shut up", "be quiet"], "de": ["ruhig"], "ta": ["அமைதி"]},
}

# ─── SIMULATOR SETTINGS ──────────────────────────────────────────
SIM_ROOM_WIDTH = 8.0       # meters
SIM_ROOM_DEPTH = 6.0       # meters
SIM_WEB_PORT = 5002        # 3D web UI port
SIM_WEBSOCKET_PORT = 5003  # State broadcast port
SIM_USE_WEBCAM = True      # Use laptop webcam as Pepper camera
SIM_USE_MIC = True         # Use laptop mic as Pepper mic
SIM_BATTERY_DRAIN_MOVING = 8.0    # % per hour while moving
SIM_BATTERY_DRAIN_IDLE = 4.0      # % per hour while idle

# ─── PEPPER JOINT LIMITS (radians) — from NAOqi 2.5 docs ─────────
PEPPER_JOINTS = {
    "HeadYaw":        {"min": -2.0857, "max": 2.0857},
    "HeadPitch":      {"min": -0.7068, "max": 0.6371},
    "LShoulderPitch": {"min": -2.0857, "max": 2.0857},
    "LShoulderRoll":  {"min": 0.0087,  "max": 1.5621},
    "LElbowYaw":      {"min": -2.0857, "max": 2.0857},
    "LElbowRoll":     {"min": -1.5621, "max": -0.0087},
    "LWristYaw":      {"min": -1.8239, "max": 1.8239},
    "LHand":          {"min": 0.0,     "max": 1.0},
    "RShoulderPitch": {"min": -2.0857, "max": 2.0857},
    "RShoulderRoll":  {"min": -1.5621, "max": -0.0087},
    "RElbowYaw":      {"min": -2.0857, "max": 2.0857},
    "RElbowRoll":     {"min": 0.0087,  "max": 1.5621},
    "RWristYaw":      {"min": -1.8239, "max": 1.8239},
    "RHand":          {"min": 0.0,     "max": 1.0},
    "HipRoll":        {"min": -0.5149, "max": 0.5149},
    "HipPitch":       {"min": -1.0385, "max": 1.0385},
    "KneePitch":      {"min": -0.5149, "max": 0.5149},
}

# ─── PEPPER PHYSICAL SPECS ────────────────────────────────────────
PEPPER_MAX_SPEED = 0.35         # m/s
PEPPER_MAX_ROTATION_SPEED = 1.0 # rad/s
PEPPER_HEIGHT = 1.21            # meters
PEPPER_WEIGHT = 28.0            # kg
