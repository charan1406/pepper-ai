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

## Quick Start

### Prerequisites
- Python 3.11+
- [llama.cpp](https://github.com/ggml-org/llama.cpp) built with CUDA
- Qwen3.5 GGUF models in `~/models/` (or set `PEPPER_MODEL_DIR`)
- 4GB+ VRAM GPU (dev) or 6GB+ (production)

### Setup

```bash
git clone https://github.com/charan1406/pepper-ai.git
cd pepper-ai

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For PyTorch CPU-only (saves VRAM for LLMs):
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Download Models

```bash
# Qwen3.5 (from HuggingFace)
mkdir -p ~/models
# Download Qwen3.5-4B-Q4_K_M.gguf and Qwen3.5-0.8B.Q4_K_M.gguf
# from https://huggingface.co/ggml-org/
```

### Run

```bash
# 1. Start LLM brains
./start_dev.sh both

# 2. Start simulator bridge (mock Pepper)
./simulator/start_bridge.sh

# 3. Run main application
python main.py
```

### Tests

```bash
python test_phase1.py   # Bridge + LLM tests
python test_phase2.py   # Perception tests (needs bridge running)
```

## Configuration

All settings are in `config.py`. Override via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PEPPER_BRIDGE_URL` | `http://localhost:5001` | Bridge server URL |
| `PEPPER_MODEL_DIR` | `~/models` | Path to GGUF model files |
| `PEPPER_IP` | `192.168.1.100` | Real Pepper robot IP |

Or create `config.local.py` to override any setting.

## Project Structure

```
pepper-ai/
├── main.py                 # Entry point
├── config.py               # Central configuration
├── pepper/                 # Bridge client (HTTP API)
├── brains/                 # LLM client + reflex keywords
├── core/                   # Router, orchestrator, behavior tree, supervisor
├── perception/             # STT, YOLO, face recognition, scene manager
├── memory/                 # Obsidian vault read/write
├── tools/                  # Web search
├── tts/                    # TTS routing (native + edge-tts)
├── simulator/              # Mock bridge + 3D web frontend
├── pepper_brain/           # Obsidian vault (Pepper's memory)
├── test_phase1.py          # Phase 1 tests
├── test_phase2.py          # Phase 2 tests
└── start_dev.sh            # Launch LLM servers (4GB VRAM)
```

## Hardware Requirements

| Mode | GPU | RAM | Notes |
|------|-----|-----|-------|
| Dev (simulator) | 4GB VRAM | 8GB | Both brains on shared GPU |
| Production | 6GB VRAM | 16GB | Full offload + real Pepper |

## Tech Stack

- **LLM**: Qwen3.5-4B + 0.8B via llama.cpp
- **STT**: faster-whisper (small) + Silero VAD
- **Vision**: YOLO26n (ultralytics) + InsightFace (ArcFace)
- **Memory**: Obsidian-compatible markdown with [[backlinks]]
- **Autonomy**: py_trees behavior tree
- **TTS**: Pepper native + edge-tts fallback

## License

MIT
