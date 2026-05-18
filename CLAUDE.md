# CLAUDE.md — Pepper AI Project Context

## Karpathy Principles — Read This First
These are the operating rules for every Claude Code session on this project.

### 1. Read before write
Before changing any file, read the relevant section first. Never guess at what exists.
Use grep to find the right location, then read that range. Never load 500 lines when you need 20.

### 2. Small, targeted changes
Every edit should be the smallest possible diff that achieves the goal.
One logical change per edit block. If a fix touches 4 files, pause and ask whether it should be split.

### 3. Verify, don't assume
If you think a variable is named X, grep for it before using it.
If you think a function exists, check before calling it.
False confidence causes cascading bugs — one wrong assumption + one edit = two bugs.

### 4. Success criteria before implementation
Before writing any code, state explicitly:
- What the working state looks like
- How you'll verify it worked
- What the rollback is if it breaks

Format:
```
Goal: [what we're changing]
Success: [observable outcome — log line, output, metric]
Verify: [exact command to confirm]
Rollback: [how to undo]
```

### 5. Plan → implement → verify loop
For any non-trivial change:
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Never chain multiple unverified changes. Each step must pass before the next starts.

### 6. Don't over-engineer
Match complexity to the problem. A 5-line fix is better than a 50-line abstraction.
If you're building infrastructure for a single use case, stop and ask.

---

## Project Overview
Building a production-grade system connecting a **Pepper 1.8 robot** (NAOqi 2.5) to a local **Qwen3.5-4B LLM**. Two-tier architecture (reflex + 4B brain + pre-cached filler audio), Obsidian-compatible memory with [[backlinks]], 3D web simulator for offline testing. University project in Germany, targeting production quality for grades.

## Hardware
- **Dev laptop**: RTX 3050 4GB VRAM, Arch Linux, kitty terminal, zsh
- **Production**: 6GB VRAM GPU + real Pepper 1.8 robot
- **Models at**: `/home/astronox/models/` — Qwen3.5-4B-Q4_K_M.gguf, mmproj-F16.gguf
- **llama-server at**: `/home/astronox/llama.cpp/build/bin/llama-server`

## Architecture

### Two-Tier System
1. **REFLEX** (~100ms): Keyword matcher for movement commands → direct bridge call
2. **BRAIN** (4B, 18 tok/s on dev): All LLM work — social, factual, vision, memory, web search, tool calls
3. **FILLER** (~10ms): Pre-cached audio phrases play instantly while brain generates

### Services (dev mode)
| Service | Port | What |
|---|---|---|
| Simulator bridge | 5001 | Mock Pepper HTTP API |
| Brain (4B, ngl=24) | 8090 | Thinking ON, budget=1024, ctx=8192 |
| 3D web UI | 5002 | React + Three.js Pepper simulator |
| WebSocket state | 5003 | Real-time state to 3D frontend |

### Critical: Qwen3.5 Model Behavior
- 4B model NEEDS thinking enabled for quality output
- Pass `chat_template_kwargs: {"enable_thinking": true}` PER-REQUEST in API body
- Official sampling: temp=1.0, top_p=0.95, top_k=20, presence_penalty=1.5
- NEVER use temperature=0.0 (causes infinite loops with Qwen3.5)
- `reasoning_content` field = hidden thinking, `content` field = spoken response
- Multi-turn: strip thinking from history (only send content in past messages)
- Detailed reference: `pepper_brain/system/llm_reference.md`
- User's own Qwen3.5 audit: uploaded as `4b_arc.md` in this project context

### Qwen3.5 Tool Calling
- Uses XML format: `<tool_call>{"name":"search","arguments":{"query":"..."}}</tool_call>`
- Tools defined in `<tools>` XML tags in system prompt (Jinja template handles this)
- Pass `tools` array in API request body (OpenAI format), llama.cpp converts

## Project Structure
```
pepper-ai/
├── config.py                    # Central config — ports, paths, thresholds
├── start_dev.sh                 # Launch 4B brain on 4GB (ngl 24)
├── start_production.sh          # Launch 4B brain on 6GB (ngl 32 + vision)
├── chat.html                    # Browser chat interface for testing brains
├── test_phase1.py               # Phase 1 test suite + interactive chat
├── PHASE2_BUILD_GUIDE.md        # Detailed guide for building Phase 2
├── pepper/
│   ├── client.py                # ✅ HTTP client for bridge (all endpoints)
│   └── bridge.py                # Real NAOqi bridge (Python 2.7, for real robot)
├── brains/
│   └── llm_client.py            # ✅ Brain client (thinking, profiles, tools)
├── simulator/
│   ├── sim_bridge.py            # ✅ Mock bridge server (identical API to real)
│   ├── sim_state.py             # ✅ Physics engine (smooth movement, joints, battery)
│   ├── start_bridge.sh          # Launch bridge (creates .venv, installs deps)
│   └── web/                     # ✅ React + Three.js 3D frontend
├── pepper_brain/                # Obsidian vault — Pepper's memory
│   ├── people/_template.md      # Person file template with [[backlinks]]
│   ├── system/
│   │   ├── deep_brain.md        # 4B system prompt (Karpathy principles, grounding)
│   │   ├── autonomous_mode.md   # Idle exploration behavior spec
│   │   ├── llm_reference.md     # Qwen3.5 integration reference
│   │   ├── personality.md       # Pepper's persona
│   │   └── rules.md             # Hard behavioral rules
│   ├── environment/
│   │   ├── spatial_map.md       # Room layout with [[location]] backlinks
│   │   ├── known_objects.md     # Detected objects log
│   │   ├── observations.md      # Autonomous observation log
│   │   └── routines.md          # Learned patterns
│   └── (topics/, conversations/, knowledge/, locations/, daily_summary/, encodings/, maps/, logs/)
├── core/
│   ├── router.py                # ✅ Two-tier routing (reflex/deep)
│   ├── orchestrator.py          # ✅ Main loop: perception → route → brain → speak
│   ├── behavior_tree.py         # ✅ py_trees autonomous behavior (exploration, idle)
│   ├── supervisor.py            # ✅ Circuit breaker + graceful degradation
│   ├── health.py                # ✅ Structured JSON logging + metrics
│   └── watchdog.py              # ✅ Separate process heartbeat monitor
├── perception/
│   ├── stt.py                   # ✅ faster-whisper + Silero VAD
│   ├── vision.py                # ✅ YOLO26n + InsightFace (dlib fallback)
│   └── scene.py                 # ✅ Background scene state manager
├── memory/
│   ├── vault.py                 # ✅ Obsidian vault read/write + backlinks
│   └── person.py                # ✅ Person CRUD + quick context for LLM
├── tools/
│   └── web_search.py            # ✅ DuckDuckGo + caching
├── tts/
│   ├── router.py                # ✅ Pepper native + edge-tts fallback
│   └── filler.py                # ✅ Pre-cached filler audio for instant playback
├── brains/
│   ├── llm_client.py            # ✅ Brain client (thinking, profiles, tools)
│   └── reflex.py                # ✅ Keyword-matched instant commands
├── main.py                      # ✅ Entry point (orchestrator + BT + health)
├── test_phase1.py               # ✅ Phase 1 tests + interactive chat
└── test_phase2.py               # ✅ Phase 2 perception tests
```

## Build Phases
1. ✅ **Phase 1**: Bridge client + LLM client
2. ✅ **Phase 2**: Perception — faster-whisper STT + YOLO26n + InsightFace
3. ✅ **Phase 3**: Router + Reflex (keyword matching, two-tier routing)
4. ✅ **Phase 4**: Memory (Obsidian vault read/write with backlinks)
5. ✅ **Phase 5**: Orchestrator (main loop, wires everything)
6. ✅ **Phase 6**: Web search + TTS routing
7. ✅ **Phase 7**: Autonomous exploration (py_trees behavior tree)
8. ✅ **Phase 8**: Production hardening (circuit breaker, watchdog, logging)

## Research-Based Upgrades (May 2026)
- **YOLO26n** replaces YOLOv8n: 43% faster CPU inference (38.9ms vs 80ms), mAP 40.9
- **InsightFace** replaces dlib: no compilation, ONNX-only, ArcFace embeddings
- **py_trees** behavior tree for autonomous exploration (utility-scored zones)
- **Circuit breaker** pattern on all LLM calls with 4-level degradation ladder
- **Structured JSON logging** with daily rotation + heartbeat watchdog
- DuckDuckGo API confirmed still free/working; Brave/Tavily as future upgrade
- Silero VAD stays (torch.hub) — silero-vad-lite doesn't support Python 3.14 yet
- Qwen3.6 released (April 2026) but staying on Qwen3.5 for stability

## Key Design Principles (Karpathy)
1. Ground everything — never hallucinate, always use tools/memory/search
2. RAG over parametric knowledge — person data from .md files, not model weights
3. Constrained outputs — JSON for structured data, not freeform
4. Tool use over guessing — search when uncertain
5. Express uncertainty — "I think..." when not sure

## Environment Setup
```bash
# Activate venv (required on Arch Linux)
cd ~/Projects/pepper-ai && source .venv/bin/activate

# Start everything
./start_dev.sh               # 4B brain on 4GB VRAM
./simulator/start_bridge.sh  # Simulator bridge
cd simulator && ./start_web.sh  # 3D frontend

# Test
python test_phase1.py

# Kill brains
lsof -ti:8090 | xargs kill -9
```

## Conventions
- Python 3.11+ for all middleware, Python 2.7 ONLY for pepper/bridge.py
- All file I/O done by Python code, never by the LLM
- Obsidian backlinks: `[[people/john_smith|John]]` format
- spoken_text property handles cleanup of reasoning leaks from small models
- Atomic file writes for memory (.tmp → rename)
- pip install with `--break-system-packages` or use .venv
