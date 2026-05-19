# Pepper AI — LLM-Powered Social Robot

A production-grade system connecting a **Pepper 1.8 robot** (NAOqi 2.5) to a local **Qwen3.5-4B** LLM. Two-tier architecture (reflex + brain) with agentic tool calling, Obsidian-compatible memory, offline TTS, and a 3D web simulator for offline testing.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Orchestrator                       │
│  ┌─────────┐   ┌──────────────────────────────────┐  │
│  │ Reflex  │   │         Brain (4B Qwen3.5)       │  │
│  │ ~100ms  │   │  thinking=ON, agentic tool loop  │  │
│  │ keywords│   │  web search, auto-continue       │  │
│  └─────────┘   └──────────────────────────────────┘  │
│         ▲                    ▲                        │
│         └────────────────────┘                        │
│                   Router                              │
├──────────────────────────────────────────────────────┤
│  Perception          │  Memory         │  Actions     │
│  • faster-whisper    │  • Obsidian     │  • Speech    │
│  • Silero VAD        │  • FTS5 search  │  • Movement  │
│  • YOLO26n           │  • Person files │  • Gestures  │
│  • InsightFace       │  • Backlinks    │  • Navigation│
│  • Scene Manager     │  • Enrollment   │  • Eyes LED  │
├──────────────────────────────────────────────────────┤
│  TTS                 │  Tools                         │
│  • Kokoro-82M (GPU)  │  • SearXNG web search          │
│  • Pepper native     │  • Agentic loop (3 rounds)     │
│  • edge-tts fallback │  • Auto-continue on truncation │
├──────────────────────────────────────────────────────┤
│  Production                                           │
│  • Behavior Tree (py_trees) — autonomous exploration  │
│  • Circuit Breaker — graceful degradation             │
│  • Watchdog — auto-restart on hang                    │
│  • Structured JSON logging                            │
└──────────────────────────────────────────────────────┘
```

---

## Hardware Requirements

| Mode | GPU VRAM | RAM | Notes |
|------|----------|-----|-------|
| Dev (simulator) | 4GB+ | 8GB+ | Partial GPU offload, CPU TTS |
| Production (real Pepper) | 6GB+ | 16GB+ | Full GPU offload + vision + GPU TTS |

Tested on:
- **Dev**: RTX 3050 (4GB VRAM), Arch Linux
- **Production**: RTX 3060 (6GB VRAM) + Pepper 1.8 robot

---

## Quick Start

### 1. System Dependencies

**Arch Linux:**
```bash
sudo pacman -S base-devel cmake git python python-pip nodejs npm cuda cudnn espeak-ng
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install build-essential cmake git python3 python3-pip python3-venv \
    nodejs npm nvidia-cuda-toolkit libcudnn8 libcudnn8-dev espeak-ng
```

### 2. Build llama.cpp with CUDA

```bash
cd ~
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
git checkout cf8b0dbda  # Pinned build 8861 — tested and stable
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j$(nproc)
```

### 3. Download Models

```bash
mkdir -p ~/models && cd ~/models

# Brain — Qwen3.5-4B (Opus-distilled, ~2.6 GB)
# Download Q4_K_M from: https://huggingface.co/Jackrong/Qwen3.5-4B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF

# Kokoro TTS — offline text-to-speech (~115 MB total)
wget -O kokoro-v1.0.int8.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
wget -O voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Vision projector (optional, production 6GB+ only)
# Download mmproj-F16.gguf from the 4B model repo
```

### 4. Set Up Pepper AI

```bash
cd ~/Projects
git clone https://github.com/charan1406/pepper-ai.git
cd pepper-ai

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install kokoro-onnx soundfile  # Offline TTS
pip install edge-tts               # Online TTS fallback

# For production GPU TTS:
pip install onnxruntime-gpu  # Replaces onnxruntime for CUDA support
```

### 5. Run

```bash
# Terminal 1 — Start the brain
./start_dev.sh                    # 4GB dev mode
# or: ./start_production.sh      # 6GB prod mode (GPU TTS, distil-whisper, vision)

# Terminal 2 — Simulator bridge
./simulator/start_bridge.sh

# Terminal 3 — 3D web frontend (optional)
cd simulator && ./start_web.sh    # Opens at http://localhost:5002

# Terminal 4 — Main application
source .venv/bin/activate
python main.py
```

---

## Services

| Service | Port | Command |
|---------|------|---------|
| Brain (4B Qwen3.5) | 8090 | `./start_dev.sh` |
| Simulator Bridge | 5001 | `./simulator/start_bridge.sh` |
| 3D Web UI | 5002 | `./simulator/start_web.sh` |
| WebSocket State | 5003 | (started by bridge) |

---

## Configuration

All settings in `config.py`. Override via environment variables or `config.local.py`.

### Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PEPPER_BRIDGE_URL` | `http://localhost:5001` | Bridge server URL |
| `PEPPER_MODEL_DIR` | `~/models` | Path to model files |
| `PEPPER_IP` | `192.168.1.100` | Real Pepper robot IP |
| `PEPPER_KOKORO_GPU` | `false` | Enable GPU TTS (set `true` on 6GB+) |
| `PEPPER_WHISPER_MODEL` | `small` | STT model (`distil-large-v3` for prod) |
| `SEARX_URL` | `http://localhost:8080/search` | SearXNG instance URL |

### Dev vs Production

| Feature | Dev (4GB) | Production (6GB) |
|---------|-----------|-------------------|
| GPU layers | ngl=99 | ngl=99 |
| Vision (mmproj) | Off | On |
| TTS | Kokoro CPU (fillers) + edge-tts | Kokoro GPU (all TTS, offline) |
| STT | whisper-small | distil-large-v3 |
| Context | 8192 tokens | 8192 tokens |

### Qwen3.5 Critical Notes

- **Thinking must be enabled** for quality output — `enable_thinking: true` sent per-request
- **Never use `temperature=0.0`** — causes infinite repetition loops (minimum 0.1)
- Official sampling: `temp=1.0, top_p=0.95, top_k=20, presence_penalty=1.5`
- `reasoning_content` = hidden thinking, `content` = spoken response

---

## Project Structure

```
pepper-ai/
├── main.py                 # Entry point — orchestrator + BT + health
├── config.py               # Central config (ports, paths, budgets)
├── start_dev.sh            # Brain on 4GB VRAM (pinned llama.cpp b8861)
├── start_production.sh     # Brain on 6GB + GPU TTS + distil-whisper + vision
├── chat.html               # Browser chat for quick LLM testing
│
├── pepper/                 # Bridge client
│   ├── client.py           # HTTP client for Pepper API
│   └── bridge.py           # Real NAOqi bridge (Python 2.7)
│
├── brains/                 # LLM interface
│   ├── llm_client.py       # httpx client (streaming, tool parsing, profiles)
│   └── reflex.py           # Keyword-matched instant commands
│
├── core/                   # Control logic
│   ├── orchestrator.py     # Agentic loop: perception → route → tools → speak
│   ├── router.py           # Two-tier routing (reflex / brain)
│   ├── behavior_tree.py    # py_trees autonomous exploration
│   ├── supervisor.py       # Circuit breaker + graceful degradation
│   ├── health.py           # Structured JSON logging + metrics
│   └── watchdog.py         # Separate process heartbeat monitor
│
├── perception/             # Sensor processing
│   ├── stt.py              # faster-whisper + Silero VAD
│   ├── vision.py           # YOLO26n + InsightFace + face enrollment
│   └── scene.py            # Background scene state manager
│
├── memory/                 # Obsidian vault interface
│   ├── vault.py            # FTS5-indexed vault + backlinks
│   └── person.py           # Person CRUD + quick context for LLM
│
├── tools/
│   └── web_search.py       # SearXNG search + caching
│
├── tts/
│   ├── router.py           # Kokoro-82M (GPU/CPU) + Pepper native + edge-tts
│   └── filler.py           # Pre-cached filler audio for instant playback
│
├── simulator/              # Offline development
│   ├── sim_bridge.py       # Mock bridge (same API as real Pepper)
│   ├── sim_state.py        # Physics engine (movement, joints, battery)
│   └── web/                # React + Three.js + Vite 3D frontend
│
├── pepper_brain/           # Obsidian vault — Pepper's memory
│   ├── system/             # System prompts, rules, personality
│   ├── people/             # Person files (auto-created on enrollment)
│   ├── environment/        # Spatial map, objects, observations
│   └── ...                 # topics, conversations, knowledge, etc.
│
├── test_phase1.py          # Bridge + LLM tests
└── test_phase2.py          # Perception tests
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM Inference | [llama.cpp](https://github.com/ggml-org/llama.cpp) (build 8861, pinned) |
| Brain | Qwen3.5-4B (Opus-distilled, Q4_K_M) |
| LLM Client | httpx (sync + streaming) |
| Web Search | [SearXNG](https://github.com/searxng/searxng) (self-hosted) |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + Silero VAD |
| Object Detection | [YOLO26n](https://docs.ultralytics.com/) |
| Face Recognition | [InsightFace](https://github.com/deepinsight/insightface) (ArcFace, ONNX) |
| Memory | Obsidian markdown + SQLite FTS5 search index |
| TTS | [Kokoro-82M](https://github.com/thewh1teagle/kokoro-onnx) + Pepper native + edge-tts |
| Behavior Tree | [py_trees](https://github.com/splintered-reality/py_trees) |
| 3D Simulator | React + Three.js + Vite |

---

## Connecting a Real Pepper Robot

1. Set the robot's IP:
   ```bash
   export PEPPER_IP=192.168.1.100
   ```

2. Run the NAOqi bridge (Python 2.7):
   ```bash
   python2 pepper/bridge.py
   ```

3. Use `start_production.sh` for full GPU offload + vision + GPU TTS.

4. The bridge exposes the same HTTP API as the simulator — the rest of the stack works unchanged.

---

## Tests

```bash
source .venv/bin/activate

# Phase 1: bridge + LLM (requires brains + bridge running)
python test_phase1.py

# Phase 2: perception pipeline
python test_phase2.py
```

---

## License

MIT
