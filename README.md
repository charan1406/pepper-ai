# Pepper AI — LLM-Powered Social Robot

A production-grade system connecting a **Pepper 1.8 robot** (NAOqi 2.5) to local **Qwen3.5** LLMs. Three-brain architecture with Obsidian-compatible memory, 3D web simulator, and autonomous exploration.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Orchestrator                        │
│  ┌─────────┐   ┌─────────┐   ┌──────────────────┐   │
│  │  Reflex │   │  Fast   │   │   Deep Brain     │   │
│  │ ~100ms  │   │  0.8B   │   │   4B (Qwen3.5)   │   │
│  │ keywords│   │  social │   │   factual/tools   │   │
│  └─────────┘   └─────────┘   └──────────────────┘   │
│         ▲            ▲               ▲                │
│         └────────────┴───────────────┘                │
│                      Router                           │
├──────────────────────────────────────────────────────┤
│  Perception          │  Memory         │  Actions     │
│  • Whisper STT       │  • Obsidian     │  • Speech    │
│  • YOLO26n           │  • Person files │  • Movement  │
│  • InsightFace       │  • Backlinks    │  • Gestures  │
│  • Scene Manager     │  • Vault R/W    │  • Navigation│
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
| Dev (simulator only) | 4GB+ | 8GB+ | Both brains share GPU, partial offload |
| Production (real Pepper) | 6GB+ | 16GB+ | Full GPU offload + vision model |

Tested on:
- **Dev**: RTX 3050 (4GB VRAM), Arch Linux
- **Production**: 6GB VRAM GPU + Pepper 1.8 robot

---

## Full Setup Guide

Follow these steps in order. By the end, you'll have both LLM brains running, the simulator active, and be able to chat with Pepper.

### Step 1: System Dependencies

**Arch Linux:**
```bash
sudo pacman -S base-devel cmake git python python-pip nodejs npm cuda cudnn
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install build-essential cmake git python3 python3-pip python3-venv \
    nodejs npm nvidia-cuda-toolkit libcudnn8 libcudnn8-dev
```

You need an NVIDIA GPU with CUDA support. Verify with:
```bash
nvidia-smi
```

### Step 2: Build llama.cpp with CUDA

llama.cpp is the inference engine that runs the Qwen3.5 models on your GPU.

```bash
cd ~
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp

# Build with CUDA support
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j$(nproc)
```

Verify it built correctly:
```bash
ls ~/llama.cpp/build/bin/llama-server
# Should exist. If not, check cmake output for CUDA errors.
```

**Troubleshooting:**
- `CUDA not found`: Make sure `nvcc --version` works. On Arch: `sudo pacman -S cuda`. On Ubuntu: `sudo apt install nvidia-cuda-toolkit`.
- `cudnn not found`: On Arch: `sudo pacman -S cudnn`. On Ubuntu: `sudo apt install libcudnn8-dev`.
- To build CPU-only (no GPU, much slower): use `cmake -B build` without `-DGGML_CUDA=ON`.

### Step 3: Download Models

The project uses Opus-distilled Qwen3.5 models (fine-tuned for better reasoning at small sizes).

```bash
mkdir -p ~/models
cd ~/models
```

**Deep Brain — 4B model** (main reasoning brain):
```bash
# Download from: https://huggingface.co/Jackrong/Qwen3.5-4B-Claude-4.6-Opus-Reasoning-Distilled-v2-GGUF
# Pick the Q4_K_M quantization (~2.6 GB)
# Save as: ~/models/Qwen3.5-4B.Q4_K_M.gguf
```

**Fast Brain — 0.8B model** (instant responses, fillers):
```bash
# Download from: https://huggingface.co/Jackrong/Qwen3.5-0.8B-Claude-4.6-Opus-Reasoning-Distilled-GGUF
# Pick the Q4_K_M quantization (~0.5 GB)
# Save as: ~/models/Qwen3.5-0.8B.Q4_K_M.gguf
```

**Vision Projector (optional, production only):**
```bash
# Only needed if you have 6GB+ VRAM and want camera vision
# Download mmproj-F16.gguf from the 4B model repo
# Save as: ~/models/mmproj-F16.gguf
```

Verify all models are in place:
```bash
ls -lh ~/models/
# Should see:
#   Qwen3.5-4B.Q4_K_M.gguf   (~2.6 GB)
#   Qwen3.5-0.8B.Q4_K_M.gguf (~0.5 GB)
#   mmproj-F16.gguf           (~0.6 GB, optional)
```

### Step 4: Clone and Set Up Pepper AI

```bash
cd ~/Projects   # or wherever you keep repos
git clone https://github.com/charan1406/pepper-ai.git
cd pepper-ai

# Create virtual environment (required on Arch Linux and recommended everywhere)
python -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install PyTorch CPU-only (saves VRAM — the LLMs use the GPU, not PyTorch)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Optional: edge-tts for text-to-speech fallback
pip install edge-tts
```

### Step 5: Start the LLM Brains

**Dev mode (4GB VRAM — both brains share GPU):**
```bash
./start_dev.sh both
```

This starts:
- **Deep Brain** (4B) on port `8090` — thinking enabled, 1024 token reasoning budget
- **Fast Brain** (0.8B) on port `8091` — thinking disabled, instant responses

Wait for both `✓ ready` messages before proceeding.

**Production mode (6GB+ VRAM):**
```bash
./start_production.sh
```

Same ports, but full GPU offload and vision projector enabled.

**Verify brains are running:**
```bash
curl http://localhost:8090/health
# {"status":"ok"}

curl http://localhost:8091/health
# {"status":"ok"}
```

**To stop the brains:**
```bash
# Ctrl+C in the terminal running start_dev.sh, or:
lsof -ti:8090 | xargs kill -9
lsof -ti:8091 | xargs kill -9
```

### Step 6: Start the Simulator

The simulator provides a mock Pepper robot with the same HTTP API as the real one, so you can develop without the physical robot.

**Terminal 2 — Simulator bridge:**
```bash
cd ~/Projects/pepper-ai
./simulator/start_bridge.sh
# Creates .venv if needed, installs deps, starts bridge on port 5001
```

**Terminal 3 — 3D web frontend (optional, needs Node.js):**
```bash
cd ~/Projects/pepper-ai/simulator
./start_web.sh
# Installs npm deps on first run, starts Vite dev server on port 5002
```

Open http://localhost:5002 in your browser to see Pepper in 3D.

### Step 7: Run Pepper AI

**Terminal 4 — Main application:**
```bash
cd ~/Projects/pepper-ai
source .venv/bin/activate
python main.py
```

This starts the orchestrator which connects perception → routing → brains → speech.

**Or test interactively:**
```bash
python test_phase1.py
# Runs automated tests, then drops into interactive chat mode
```

**Or use the browser chat interface:**
Open `chat.html` in a browser — it connects directly to the LLM brains for quick testing.

---

## Quick Reference — All Services

| Service | Port | Command | Purpose |
|---------|------|---------|---------|
| Deep Brain (4B) | 8090 | `./start_dev.sh deep` | Reasoning, tools, vision |
| Fast Brain (0.8B) | 8091 | `./start_dev.sh fast` | Fillers, greetings |
| Simulator Bridge | 5001 | `./simulator/start_bridge.sh` | Mock Pepper HTTP API |
| 3D Web UI | 5002 | `./simulator/start_web.sh` | React + Three.js viewer |
| WebSocket State | 5003 | (started by bridge) | Real-time state to frontend |

---

## Configuration

All settings are in `config.py`. Override via environment variables or create `config.local.py`.

### Key Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PEPPER_BRIDGE_URL` | `http://localhost:5001` | Bridge server URL (sim or real) |
| `PEPPER_MODEL_DIR` | `~/models` | Path to GGUF model files |
| `PEPPER_IP` | `192.168.1.100` | Real Pepper robot IP (production only) |

### llama.cpp Server Flags Explained

These are the flags used in `start_dev.sh` — understanding them helps if you need to tune for your hardware:

| Flag | What it does | Our value |
|------|-------------|-----------|
| `-m` | Model file path | `~/models/Qwen3.5-4B.Q4_K_M.gguf` |
| `-ngl` | GPU layers to offload (more = faster, uses more VRAM) | 24 (dev) / 32 (prod) |
| `-c` | Context window size (tokens) | 8192 (deep) / 2048 (fast) |
| `-np` | Parallel request slots | 1 (single user) |
| `-fa on` | Flash attention (saves VRAM) | on |
| `-ctk q4_0` | KV cache key quantization (saves VRAM) | q4_0 |
| `-ctv q4_0` | KV cache value quantization | q4_0 |
| `--jinja` | Enable Jinja chat templates (required for Qwen3.5) | always |
| `--chat-template-kwargs` | Template parameters — `enable_thinking` is critical | `true` for deep, `false` for fast |
| `--reasoning-budget` | Max thinking tokens (deep brain only) | 1024 |
| `--threads` | CPU threads for prompt processing | 8 |
| `--threads-batch` | CPU threads for batch processing | 16 |
| `--mmproj` | Vision projector model (production only) | `mmproj-F16.gguf` |

**VRAM tuning:** If you're running out of VRAM, lower `-ngl` (fewer GPU layers, more on CPU). If you have extra VRAM, raise it. Use `nvidia-smi` to monitor usage.

### Qwen3.5 Critical Notes

- **Thinking must be enabled** for the 4B model to produce quality output
- **Thinking must be disabled** for the 0.8B model (causes reasoning leaks and loops)
- **Never use `temperature=0.0`** — Qwen3.5 enters infinite repetition loops. Minimum is 0.1
- The `enable_thinking` flag is sent per-request via the API, not just as a server flag
- When thinking is enabled, the model outputs `reasoning_content` (hidden) and `content` (spoken)

---

## Project Structure

```
pepper-ai/
├── main.py                 # Entry point — orchestrator + behavior tree + health
├── config.py               # Central configuration (ports, paths, thresholds)
├── start_dev.sh            # Launch both brains on 4GB VRAM
├── start_production.sh     # Launch both brains on 6GB VRAM + vision
├── chat.html               # Browser chat interface for quick LLM testing
├── requirements.txt        # Python dependencies
│
├── pepper/                 # Bridge client
│   ├── client.py           # HTTP client for Pepper API (all endpoints)
│   └── bridge.py           # Real NAOqi bridge (Python 2.7, for real robot only)
│
├── brains/                 # LLM interface
│   ├── llm_client.py       # Dual brain client (thinking, profiles, tool parsing)
│   └── reflex.py           # Keyword-matched instant commands (no LLM)
│
├── core/                   # Control logic
│   ├── orchestrator.py     # Main loop: perception → route → brain → speak
│   ├── router.py           # Three-brain routing (reflex/fast/deep)
│   ├── behavior_tree.py    # py_trees autonomous exploration
│   ├── supervisor.py       # Circuit breaker + graceful degradation
│   ├── health.py           # Structured JSON logging + metrics
│   └── watchdog.py         # Separate process heartbeat monitor
│
├── perception/             # Sensor processing
│   ├── stt.py              # faster-whisper + Silero VAD
│   ├── vision.py           # YOLO26n + InsightFace (dlib fallback)
│   └── scene.py            # Background scene state manager
│
├── memory/                 # Obsidian vault interface
│   ├── vault.py            # Vault read/write + backlink resolution
│   └── person.py           # Person CRUD + quick context for LLM
│
├── tools/
│   └── web_search.py       # DuckDuckGo search + caching
│
├── tts/
│   └── router.py           # Pepper native TTS + edge-tts fallback
│
├── simulator/              # Offline development environment
│   ├── sim_bridge.py       # Mock bridge server (same API as real Pepper)
│   ├── sim_state.py        # Physics engine (movement, joints, battery)
│   ├── start_bridge.sh     # Launch simulator bridge
│   ├── start_web.sh        # Launch 3D web frontend
│   └── web/                # React + Three.js + Vite frontend
│
├── pepper_brain/           # Obsidian vault — Pepper's memory and personality
│   ├── system/             # System prompts and rules
│   │   ├── deep_brain.md   # 4B system prompt
│   │   ├── fast_brain.md   # 0.8B system prompt
│   │   ├── personality.md  # Pepper's character traits
│   │   ├── rules.md        # Hard behavioral rules
│   │   └── llm_reference.md # Qwen3.5 integration reference
│   ├── people/             # Person memory files (auto-created)
│   ├── environment/        # Spatial map, objects, observations
│   └── ...                 # topics, conversations, knowledge, etc.
│
├── test_phase1.py          # Phase 1 tests (bridge + LLM)
└── test_phase2.py          # Phase 2 tests (perception)
```

---

## Tests

```bash
source .venv/bin/activate

# Phase 1: bridge connectivity + LLM response quality
# Requires: brains running (start_dev.sh) + simulator bridge
python test_phase1.py

# Phase 2: perception pipeline (STT, vision, scene)
# Requires: bridge running
python test_phase2.py
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM Inference | [llama.cpp](https://github.com/ggml-org/llama.cpp) | Runs GGUF models on GPU/CPU |
| Deep Brain | Qwen3.5-4B (Opus-distilled, Q4_K_M) | Reasoning, tools, vision |
| Fast Brain | Qwen3.5-0.8B (Opus-distilled, Q4_K_M) | Fillers, greetings |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (small) | Speech-to-text |
| VAD | Silero VAD (via torch.hub) | Voice activity detection |
| Object Detection | [YOLO26n](https://docs.ultralytics.com/) | Real-time object detection |
| Face Recognition | [InsightFace](https://github.com/deepinsight/insightface) (ArcFace) | Face ID via ONNX |
| Memory | Obsidian-compatible markdown with `[[backlinks]]` | Persistent knowledge base |
| Behavior Tree | [py_trees](https://github.com/splintered-reality/py_trees) | Autonomous exploration |
| TTS | Pepper native + [edge-tts](https://github.com/rany2/edge-tts) fallback | Text-to-speech |
| 3D Simulator | React + Three.js + Vite | Browser-based Pepper sim |

---

## Connecting a Real Pepper Robot

For production use with the physical Pepper 1.8:

1. Set the robot's IP in `config.py` or via environment variable:
   ```bash
   export PEPPER_IP=192.168.1.100
   export PEPPER_BRIDGE_URL=http://localhost:5001  # or direct to robot
   ```

2. Run `pepper/bridge.py` on a machine with NAOqi Python SDK (Python 2.7):
   ```bash
   python2 pepper/bridge.py
   ```

3. Use `start_production.sh` instead of `start_dev.sh` for full GPU offload + vision.

4. The bridge exposes the same HTTP API as the simulator, so the rest of the stack works unchanged.

---

## License

MIT
