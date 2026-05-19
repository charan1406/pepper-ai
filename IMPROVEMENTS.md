# Pepper AI — Research-Backed Improvements

> Based on papers, benchmarks, and real-world failure analysis (May 2026)
> Includes findings from "Low-Latency LLM-driven Multimodal Interaction on Pepper" (arXiv 2603.21013)

---

## Tier 1 — Fix What's Broken

### 1. Replace DuckDuckGo with SearXNG
**Problem:** DuckDuckGo instant answer API only returns Wikipedia abstracts and "related topics". Can't answer weather, news, prices, or most factual queries. Fundamentally broken for real use.
**Fix:** Hit the SearXNG instance already running in JARVIS's Docker stack (`http://localhost:8080/search?q=...&format=json`). Returns real search results with snippets and URLs. Zero cost, unlimited queries.
**Effort:** 30 minutes — rewrite `tools/web_search.py` to use SearXNG instead of DDG.

### 2. Pin llama.cpp Build
**Problem:** Tracking master introduces regressions. Known crashes: prompt cache serialization with Qwen3.5 (#21762), tensor bounds issues with speculative decoding on Qwen models.
**Fix:** Pin to build b9079 or freeze a tested commit. Document in start_dev.sh.
**Evidence:** [llama.cpp weekly reports](https://buttondown.com/weekly-project-news/) — breaking changes every 1-2 weeks.

### 3. Wire Tool Calling (Currently Skeleton Only)
**Problem:** System prompt defines tools (search, memory_update, navigate_to, tablet_show). LLM client parses `<tool_call>` XML. But nothing executes them — tool calls are parsed and discarded.
**Fix:** Add tool execution handlers in the orchestrator. Start with just `web_search` — highest impact, already has a module.
**Evidence:** [Swiss Pepper paper](https://arxiv.org/html/2603.21013v1) shows full tool loop on Pepper: LLM chains look_at → analyze_vision → describe. Their ToolRegistry pattern is proven.

### 4. Add Observation Masking
**Problem:** No context management. Just keeps last N messages by count. Long conversations overflow the 8192 context window, especially with person memory and scene text injected.
**Fix:** Implement 10-turn observation masking — replace tool outputs older than 10 turns with `[Output Omitted]`, keep reasoning/action history. Port JARVIS's `_mask_history()` but use turn-based window instead of budget-based.
**Evidence:** [The Complexity Trap](https://arxiv.org/abs/2508.21433) (NeurIPS 2025, JetBrains/TUM) — masking halves cost, matches LLM summarization, tested on Qwen3.

### 5. Enforce Token Budgets
**Problem:** Config defines TOKEN_BUDGET_* for every context block (400 system, 350 person memory, 1500 search, 2000 conversation) but no code enforces them. Large person memory or search results can silently overflow context.
**Fix:** Add token estimation (chars/3.5 like JARVIS, or use llama-server's `/tokenize` endpoint for accuracy). Truncate each block to its budget before building the message array.

---

## Tier 2 — Major Capability Upgrades

### 6. Async Streaming LLM Client
**Problem:** `brains/llm_client.py` uses synchronous `urllib.request.urlopen`. Blocks the entire thread for 2-4 seconds per request. Can't stream tokens, can't do anything else while waiting.
**Fix:** Switch to `httpx` async client with streaming. Yield tokens as they arrive. Enables real-time response display in simulator chat, and unblocks the main loop for concurrent perception.
**Evidence:** JARVIS already does this with `httpx.AsyncClient.stream()`. The Swiss Pepper paper uses streaming S2S for <2s response latency vs. Pepper's typical 3.8-9.0s cascaded pipeline.

### 7. Agentic Tool Loop
**Problem:** Single-shot LLM call. Brain can't search, read results, and then respond based on them. Every query gets one attempt.
**Fix:** Port JARVIS's agentic loop pattern:
```
while round < max_rounds:
    response = llm.chat(messages, tools=schemas)
    if response.has_tool_calls:
        execute tools → append results to messages → continue
    else:
        break  # final answer
```
**Cap at 3-4 rounds for 4B** — research shows 4B models lose coherence after 2-3 tool steps.
**Evidence:** [Function calling guide](https://insiderllm.com/guides/function-calling-local-llms/) — "for multi-step agents requiring reliability, use 14B+ or accept that smaller ones lose coherence after 2-3 steps."

### 8. GBNF Grammar for Tool Call JSON
**Problem:** Tool call parsing relies on regex matching `<tool_call>{...}</tool_call>`. Model sometimes outputs malformed JSON, incomplete arguments, or markdown fences.
**Fix:** Use llama.cpp GBNF grammar constrained decoding when requesting tool calls. Guarantees syntactically valid JSON at the token level.
**Caveat:** Can degrade content quality by up to 24%. Draft-Conditioned Constrained Decoding (arXiv 2603.03305, Feb 2026) fixes this — watch for llama.cpp integration.
**Evidence:** [llama.cpp grammar docs](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)

### 9. SQLite FTS5 + Vector Hybrid for Vault Search
**Problem:** `vault.search()` does brute-force file scanning with `query.lower() in text.lower()`. Slow on large vaults, misses semantic matches.
**Fix:** Add a SQLite sidecar database alongside the vault. FTS5 for full-text BM25 search + sqlite-vec for 384-dim embeddings. Index vault files at startup, update on write. Query both, merge with weighted scoring (60% FTS5, 40% vector).
**Keep the .md files as source of truth** — SQLite is just an index.
**Evidence:**
- [ZeroClaw hybrid architecture](https://zeroclaws.io/blog/zeroclaw-sqlite-fts5-vector-hybrid-memory-explained/)
- [Building a RAG on SQLite](https://blog.sqlite.ai/building-a-rag-on-sqlite)

### 10. Kokoro-82M for Local TTS
**Problem:** Filler audio pre-caches edge-tts output (requires internet at startup). Response TTS also depends on edge-tts (online) or Pepper native (limited quality).
**Fix:** Integrate Kokoro-82M as primary TTS engine. 82M params, sub-300ms latency, runs on CPU, near-human quality with emotional expression. Use for both filler pre-caching and response TTS. Keep edge-tts as online fallback.
**Evidence:** [TTS Models 2026](https://www.codesota.com/guides/tts-models) — Kokoro-82M best for local deployment.

---

## Tier 3 — Research-Grade Improvements

### 11. Port Swiss Group's ToolRegistry Pattern
**Paper:** [Low-Latency LLM-driven Multimodal Interaction on Pepper](https://arxiv.org/html/2603.21013v1) (March 2026)
**Their open-source code:** [pepper-android-realtime-chat](https://github.com/studerus/pepper-android-realtime-chat)

Key patterns to port:
- **Vision chaining:** "What do you see at the ceiling?" → LLM calls `look_at_position(up)` → `analyze_vision()` → describes. Multi-step tool composition.
- **Touch sensor events:** `[User touched my right hand]` → injected into LLM context → socially appropriate response.
- **Movement failure recovery:** Navigation fails → auto-trigger `analyze_vision` → reason about obstacles.
- **Function cards UI:** Tool invocations render as expandable cards showing execution details.

### 12. Connect Vision Pipeline to LLM
**Problem:** YOLO26n + InsightFace pipeline exists and works. Scene manager updates every second. But vision frames never reach the LLM — `[VISION]` block in deep_query() is always None.
**Fix:** On vision-related queries (detected via keywords or router), capture a frame, send to multimodal LLM (requires ENABLE_MMPROJ=True + 6GB VRAM), or describe the scene via YOLO detections as structured text.
**Evidence:** Swiss paper chains `analyze_vision` as a tool call. Simpler approach: always inject `[SCENE]` text from YOLO detections (already partly done).

### 13. Activate Behavior Tree
**Problem:** `behavior_tree.py` is complete (safety, engagement, exploration, idle animation) but never ticked. `main.py` has the code but it's gated behind a flag that's never set.
**Fix:** Wire `tree.tick()` into the main loop when no person is detected. Requires connecting behavior tree blackboard to scene manager state.

### 14. Person Enrollment Workflow
**Problem:** `vision.py.enroll_face()` exists but is never called. No way to register new people.
**Fix:** On first meeting (unknown face detected + conversation), prompt user for name, save face encoding to `pepper_brain/encodings/{name}.npy`, create person file from template.

### 15. Auto-Continue on Truncation
**Problem:** If LLM output is truncated (finish_reason=length, unclosed code blocks, mid-sentence), Pepper just serves the partial response.
**Fix:** Port JARVIS's `_is_truncated()` detection + auto-continue logic. Append "Continue from where you stopped" and re-query. Cap at 3 auto-continues.

### 16. Distil-Whisper for Lower STT Latency
**Current:** faster-whisper with `small` model.
**Upgrade:** distil-large-v3 — 5.8x faster than Whisper Large, 51% fewer params, within 1% WER. Drop-in replacement.
**Evidence:** [STT comparison 2026](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026)

### 17. Upgrade to Qwen 3.6 8B (Production GPU)
**When:** Available on the 6GB production machine.
**Why:** 0.933 F1 on tool calling (vs ~0.90 on 4B). Better multi-step coherence. Improved structured output.
**Caveat:** Qwen 3.6 currently rejects template kwargs with whitespace around colons in llama.cpp. Wait for fix.
**Evidence:** [Open-Source LLMs 2026](https://huggingface.co/blog/daya-shankar/open-source-llms)

---

## Key Research Sources

| Topic | Source |
|---|---|
| Pepper + LLM (direct reference) | [Low-Latency LLM on Pepper — arXiv 2603.21013](https://arxiv.org/html/2603.21013v1) |
| Context management | [The Complexity Trap — JetBrains/TUM, NeurIPS 2025](https://arxiv.org/abs/2508.21433) |
| Tool calling reliability | [InsiderLLM Function Calling Guide](https://insiderllm.com/guides/function-calling-local-llms/) |
| Hybrid memory | [ZeroClaw SQLite FTS5+Vector](https://zeroclaws.io/blog/zeroclaw-sqlite-fts5-vector-hybrid-memory-explained/) |
| Keyword vs vector RAG | [arXiv 2602.23368](https://arxiv.org/pdf/2602.23368) |
| Grammar decoding | [GBNF docs](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) |
| Draft-Conditioned Decoding | [arXiv 2603.03305](https://arxiv.org/pdf/2603.03305) |
| Parallel tool calling | [SimpleTool — arXiv 2603.00030](https://arxiv.org/abs/2603.00030) |
| TTS comparison | [CodeSOTA TTS Models 2026](https://www.codesota.com/guides/tts-models) |
| STT comparison | [Local Whisper STT 2026](https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026) |
| Social robots + LLM | [Springer — LLM Agent Architectures](https://link.springer.com/chapter/10.1007/978-3-032-07175-0_26) |
| Embodied AI survey | [arXiv 2508.05294](https://arxiv.org/html/2508.05294v4) |
| Speculative decoding | [Qwen3.6 spec decode benchmark](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090) |
| Edge RAG | [RAGdb — arXiv 2602.22217](https://arxiv.org/pdf/2602.22217) |
