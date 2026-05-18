# JARVIS Patterns to Apply to Pepper Simulator

## Problem 1: Thinking leaks into response
JARVIS solution: `_strip_think()` — regex strips `<think>...</think>` tags from streamed text.
```python
def _strip_think(text):
    cleaned = re.sub(r"<think>[\s\S]*?</think>\s*", "", text)  # closed tags
    cleaned = re.sub(r"<think>[\s\S]*$", "", cleaned)           # unclosed (streaming)
    return cleaned
```
Pepper's `_extract_from_thinking()` is a BAD fallback — it guesses the "answer" from thinking text.
FIX: Strip think tags properly. If content is still empty after stripping, return a safe fallback
like "I'm not sure how to respond to that" instead of extracting from thinking.

## Problem 2: Slow thinking for simple queries  
JARVIS uses streaming (`llm.chat()` yields deltas) so user sees tokens as they arrive.
Pepper's sim_bridge uses blocking `brain.chat()` — waits for full response before returning.
FIX: Use streaming in sim_bridge. Stream response back, strip thinking in real-time.
OR: Set lower max_tokens for simple social chat (1024 instead of 16384).
OR: Use `reasoning_budget` per-request (llama.cpp supports this).

## Problem 3: Sampling params
JARVIS casual mode: temp=1.0, top_p=0.95, top_k=20, presence_penalty=1.5
Pepper's LLMClient social profile: needs to match these exact params.
CRITICAL: presence_penalty=1.5 reduces repetition/hallucination.

## Key JARVIS Architecture Differences
- Async (httpx + FastAPI) vs Pepper's sync (requests + BaseHTTPRequestHandler)
- Streaming SSE to frontend vs Pepper's blocking JSON response
- `_strip_think()` on every delta vs Pepper's post-hoc extraction
- Auto-continue on truncation (up to 3 retries)
- `_is_truncated()` detects mid-sentence cutoffs, unclosed code blocks

## What to Implement in Pepper sim_bridge
1. Add `_strip_think()` to sim_bridge (regex approach, not heuristic extraction)
2. Fix `spoken_text` in LLMClient to use regex stripping instead of `_extract_from_thinking()`
3. Lower max_tokens for social profile (512-1024 for chat, saves thinking time)
4. Set reasoning_budget lower for social queries via API body
5. Add presence_penalty=1.5 to social profile

## LLMClient.chat() Changes Needed
The `brains/llm_client.py` `chat()` method builds the API request body.
Need to add `chat_template_kwargs: {"enable_thinking": true}` per CLAUDE.md.
Need to ensure `presence_penalty` is passed through.
The `spoken_text` property should regex-strip think tags from content, not extract from thinking.

## Quick Wins (no streaming needed)
1. `_strip_think()` on response content — fixes thinking leak
2. max_tokens=512 for social profile — faster responses  
3. presence_penalty=1.5 — less hallucination
4. Safe fallback when content empty — "Let me try again" not thinking extraction
