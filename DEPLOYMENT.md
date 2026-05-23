# Pepper AI — Deployment Guide

Full setup guide for running Pepper AI on a real Pepper 1.8 robot.

---

## Architecture Overview

```
┌──────────────┐         HTTP :5001         ┌──────────────────┐
│  Pepper 1.8  │◄──────────────────────────►│  GPU Laptop/PC   │
│  (NAOqi 2.5) │   camera, audio, motors    │  (RTX 3060 6GB)  │
│              │                            │                  │
│  bridge.py   │                            │  main.py         │
│  Python 2.7  │                            │  Python 3.11+    │
│  port 5001   │                            │                  │
└──────────────┘                            │  llama-server    │
                                            │  port 8090       │
                                            │                  │
                                            │  SearXNG         │
                                            │  port 8080       │
                                            └──────────────────┘
```

**Two machines:**
- **Pepper robot** — runs `bridge.py` (Python 2.7 + NAOqi SDK). Exposes camera, mics, motors, TTS over HTTP.
- **GPU machine** — runs everything else: LLM, STT, vision, TTS, memory, orchestrator.

They talk over HTTP on port 5001. Same WiFi network required.


---

## 1. GPU Machine Setup

### 1.1 Prerequisites

- Python 3.11+
- NVIDIA GPU with 6GB+ VRAM (RTX 3060 or better)
- CUDA toolkit installed
- Git

### 1.2 Clone and Virtual Environment

```bash
git clone https://github.com/charan1406/pepper-ai.git
cd pepper-ai

python -m venv .venv
source .venv/bin/activate
```

### 1.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

Additional packages not in requirements.txt:

```bash
# LLM client
pip install httpx

# TTS
pip install kokoro-onnx soundfile

# Speaker isolation
pip install deepfilternet resemblyzer

# Web search (edge-tts fallback, optional)
pip install edge-tts

# ONNX GPU (for Kokoro TTS on GPU)
pip install onnxruntime-gpu
```

If `onnxruntime-gpu` fails (CUDA version mismatch), try the nightly:
```bash
pip install onnxruntime-gpu --extra-index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/
```

### 1.4 Download Models

All models go in `~/models/`. Create the directory:

```bash
mkdir -p ~/models
```

| Model | File | Size | Download |
|-------|------|------|----------|
| Qwen3.5-4B (brain) | `Qwen3.5-4B.Q4_K_M.gguf` | ~2.8 GB | HuggingFace: `Qwen/Qwen3.5-4B-GGUF` |
| Qwen3.5 vision | `mmproj-F16.gguf` | ~600 MB | Same repo, multimodal projector |
| Kokoro TTS (GPU) | `kokoro-v1.0.fp16.onnx` | ~170 MB | HuggingFace: `hexgrad/Kokoro-82M-v1.0-ONNX` |
| Kokoro TTS (CPU) | `kokoro-v1.0.int8.onnx` | ~90 MB | Same repo |
| Kokoro voices | `voices-v1.0.bin` | ~30 MB | Same repo |

Whisper, YOLO, and InsightFace models download automatically on first run.

```bash
# Example download with huggingface-cli
pip install huggingface-hub
huggingface-cli download Qwen/Qwen3.5-4B-GGUF Qwen3.5-4B.Q4_K_M.gguf --local-dir ~/models
```

### 1.5 Build llama.cpp

Pinned to build 8861 (`cf8b0dbda`) — do not use latest master without testing.

```bash
cd ~
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
git checkout cf8b0dbda

cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j$(nproc)
```

Verify:
```bash
~/llama.cpp/build/bin/llama-server --version
```

### 1.6 Install SearXNG (Web Search)

SearXNG provides web search for the brain. Without it, web search tool calls silently return empty results (no crash).

```bash
# Docker (simplest)
docker run -d --name searxng -p 8080:8080 searxng/searxng

# Verify
curl "http://localhost:8080/search?q=test&format=json" | head -c 200
```

Or install natively: https://docs.searxng.org/admin/installation.html

If you skip SearXNG, the brain still works — it just can't search the web.


---

## 2. Pepper Robot Setup

### 2.1 Requirements

- Pepper 1.8 with NAOqi 2.5
- Python 2.7 with NAOqi SDK (pre-installed on Pepper)
- Network access (same WiFi as GPU machine)

### 2.2 Find Pepper's IP

Press Pepper's chest button once — it speaks its IP address.
Or check your router's DHCP table.

### 2.3 Deploy bridge.py

Copy `pepper/bridge.py` to the robot:

```bash
# From your GPU machine
scp pepper/bridge.py nao@<PEPPER_IP>:~/bridge.py
```

Default password for `nao` user: `nao`

### 2.4 Start the Bridge

SSH into Pepper and run:

```bash
ssh nao@<PEPPER_IP>
python bridge.py --ip 127.0.0.1 --port 9559 --bridge-port 5001
```

Since bridge.py runs ON the robot, it connects to NAOqi at `127.0.0.1:9559`.

You should see:
```
============================================================
  PEPPER BRIDGE — REAL NAOqi CONNECTION
  Robot: 127.0.0.1:9559
  Bridge: http://localhost:5001
============================================================
[OK] Connected to Pepper. Battery: 85%
[BRIDGE] Listening on port 5001
```

### 2.5 Verify from GPU Machine

```bash
curl http://<PEPPER_IP>:5001/health
```

Expected:
```json
{"success": true, "data": {"status": "ok", "battery": 85, "simulator": false}}
```


---

## 3. Launch Everything

### 3.1 On the Pepper Robot

```bash
ssh nao@<PEPPER_IP>
python bridge.py --ip 127.0.0.1 --bridge-port 5001
```

### 3.2 On the GPU Machine

**Terminal 1 — LLM Server:**
```bash
cd ~/Projects/pepper-ai
./start_production.sh
```

Wait until you see `llama_server: listening` before continuing.

**Terminal 2 — SearXNG (if using Docker):**
```bash
docker start searxng
```

**Terminal 3 — Pepper AI:**
```bash
cd ~/Projects/pepper-ai
source .venv/bin/activate
PEPPER_BRIDGE_URL=http://<PEPPER_IP>:5001 python main.py
```

### 3.3 Environment Variables

| Variable | Default | What |
|----------|---------|------|
| `PEPPER_BRIDGE_URL` | `http://localhost:5001` | Bridge address (set to Pepper's IP for real robot) |
| `PEPPER_IP` | `192.168.1.100` | Only used by bridge.py itself |
| `PEPPER_KOKORO_GPU` | `false` | Set `true` on 6GB+ GPU for real-time TTS |
| `PEPPER_WHISPER_MODEL` | `small` | Set `distil-large-v3` on prod for better STT |
| `PEPPER_MODEL_DIR` | `~/models` | Where model files live |
| `SEARX_URL` | `http://localhost:8080/search` | SearXNG endpoint |


---

## 4. Testing

### 4.1 Quick Smoke Test

After everything is running, speak to Pepper. The terminal should show:

```
[MAIN] Heard: "hello pepper" (person: unknown)
[MAIN] Said: "Hello! How can I help you?"
```

### 4.2 Test Individual Components

```bash
source .venv/bin/activate

# Test bridge connection
python -c "
from pepper.client import PepperClient
p = PepperClient('http://<PEPPER_IP>:5001')
print('Alive:', p.is_alive())
print('Battery:', p.battery())
"

# Test LLM
python -c "
from brains.llm_client import LLMClient
llm = LLMClient('http://localhost:8090/v1', thinking=True)
r = llm.chat('Say hello in one sentence.')
print(r.spoken_text)
"

# Test TTS
python -c "
from pepper.client import PepperClient
p = PepperClient('http://<PEPPER_IP>:5001')
p.speak('Hello, I am Pepper!')
"

# Test camera
python -c "
from pepper.client import PepperClient
p = PepperClient('http://<PEPPER_IP>:5001')
frame = p.get_camera_frame()
print('Got frame:', len(frame) if frame else 'None', 'bytes b64')
"

# Test audio recording
python -c "
from pepper.client import PepperClient
p = PepperClient('http://<PEPPER_IP>:5001')
audio = p.record_audio(seconds=3)
print('Got audio:', len(audio) if audio else 'None', 'bytes b64')
"
```

### 4.3 Interactive Chat (No Robot Needed)

Test the brain in a browser:

```bash
# With llama-server running on port 8090
# Open chat.html in a browser
xdg-open chat.html
```


---

## 5. Troubleshooting

### Bridge won't connect to Pepper

```
[ERROR] Cannot connect to Pepper: ...
```

- Check Pepper is powered on and on the same WiFi
- Verify IP: press chest button, Pepper speaks its IP
- Try: `ping <PEPPER_IP>`
- NAOqi port is 9559 by default — make sure nothing changed

### Camera returns None

```
Camera returned None
```

- Pepper's camera may need a moment after boot. Wait 30 seconds.
- Check if another process subscribed to the camera (max ~20 subscribers)
- Restart NAOqi: `ssh nao@<PEPPER_IP> "sudo /etc/init.d/naoqi restart"`

### No audio / silence from mic

- Pepper's mic volume may be low
- Adjust via: `ssh nao@<PEPPER_IP>` then use `qicli` to check ALAudioDevice
- The energy gate threshold is `0.015` RMS — if the room is very quiet, speech may be too soft. Lower `AUDIO_ENERGY_THRESHOLD` in config.py if needed

### LLM not responding

```
[ERROR] LLM timeout
```

- Check llama-server is running: `curl http://localhost:8090/v1/models`
- On 4GB VRAM: may run out of memory with vision enabled. Use `start_dev.sh` (no mmproj)
- On 6GB VRAM: `start_production.sh` should work. Check GPU memory: `nvidia-smi`

### Whisper model download hangs

First run downloads the Whisper model (~500MB for `small`, ~1.5GB for `distil-large-v3`). Needs internet. If it hangs:

```bash
# Pre-download manually
python -c "from faster_whisper import WhisperModel; WhisperModel('small')"
```

### SearXNG not working

Web search returns empty results. The brain still works, it just can't search.

```bash
# Check if SearXNG is running
curl http://localhost:8080/search?q=test&format=json

# Restart if using Docker
docker restart searxng
```

### YOLO model not found

First run downloads `yolo26n.pt` automatically. If it fails:

```bash
python -c "from ultralytics import YOLO; YOLO('yolo26n.pt')"
```

### InsightFace model not found

First run downloads `buffalo_sc` model pack. If it fails:

```bash
python -c "
import insightface
app = insightface.app.FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1, det_size=(160, 160))
"
```

### Pepper talks over itself

- `speak_and_wait()` should block until speech finishes
- If it doesn't wait, check that the bridge task tracking is working:
  ```bash
  curl http://<PEPPER_IP>:5001/speak/status
  ```
  Should return `{"is_speaking": true}` while Pepper is talking

### Out of VRAM

```
CUDA out of memory
```

- Kill other GPU processes: `nvidia-smi` then `kill <PID>`
- On 4GB: use `start_dev.sh` (text-only, no vision projector)
- On 6GB: use `start_production.sh` (vision + GPU TTS fits)
- Kokoro GPU TTS uses ~200MB VRAM. Disable with `PEPPER_KOKORO_GPU=false`

### Pepper moves into walls (autonomous mode)

The behavior tree exploration uses zone coordinates that may not match your room. Edit `core/behavior_tree.py` zone definitions to match your space, or disable autonomous mode.

The navigate endpoint falls back to `moveTo` (relative movement) when no SLAM map exists. Keep initial movements small.


---

## 6. Dev Mode (No Robot)

For development without the real robot:

```bash
cd ~/Projects/pepper-ai

# Terminal 1: Simulator bridge (uses laptop webcam + mic)
./simulator/start_bridge.sh

# Terminal 2: LLM server
./start_dev.sh

# Terminal 3: 3D web UI (optional)
cd simulator && ./start_web.sh

# Terminal 4: Main app
source .venv/bin/activate
python main.py
```

The middleware doesn't know if it's talking to the simulator or the real robot — same HTTP API.


---

## 7. File Checklist

Before running on the real robot, verify:

```bash
# Models exist
ls ~/models/Qwen3.5-4B.Q4_K_M.gguf      # Brain
ls ~/models/mmproj-F16.gguf              # Vision (6GB only)
ls ~/models/kokoro-v1.0.fp16.onnx        # TTS GPU
ls ~/models/voices-v1.0.bin              # TTS voices

# llama.cpp built
~/llama.cpp/build/bin/llama-server --version

# Python deps installed
source .venv/bin/activate
python -c "import faster_whisper, torch, ultralytics, httpx, insightface; print('OK')"

# Bridge deployed to Pepper
ssh nao@<PEPPER_IP> "ls ~/bridge.py"

# SearXNG running (optional)
curl -s http://localhost:8080/search?q=test&format=json | python -m json.tool | head -5
```


---

## 8. Ports Summary

| Port | Service | Machine |
|------|---------|---------|
| 5001 | Pepper bridge (HTTP API) | Pepper robot |
| 8090 | llama-server (LLM API) | GPU machine |
| 8080 | SearXNG (web search) | GPU machine |
| 5002 | 3D web UI (dev only) | GPU machine |
| 5003 | WebSocket state (dev only) | GPU machine |
| 9559 | NAOqi (internal) | Pepper robot |
