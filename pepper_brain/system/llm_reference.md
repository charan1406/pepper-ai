# Pepper AI — LLM Integration Reference
## How Qwen3.5 Works, How to Parse It, and How to Structure Tool Calls

---

## 1. THE ROOT CAUSE OF ALL OUR BUGS

**Qwen3.5 Small models (0.8B, 2B, 4B, 9B) have reasoning DISABLED by default.**

When we passed `--reasoning-budget 256`, we were telling llama.cpp to *cap*
reasoning at 256 tokens — but the Qwen3.5 chat template needs a separate
flag to actually *enable* thinking mode:

```
--chat-template-kwargs '{"enable_thinking":true}'
```

Without this flag, the model doesn't use `<think>` tags properly. Instead,
it outputs its reasoning as regular content — which is exactly the "leaked
reasoning" we've been fighting.

### The Two Modes of Qwen3.5

**Thinking Mode** (`enable_thinking: true`):
```
<|im_start|>assistant
<think>
The user said "hi". I should respond with a friendly greeting.
I need to keep it brief — 2 sentences max.
</think>
Hello! How are you doing today? I'm here to help.
<|im_end|>
```
- `<think>...</think>` is properly separated
- llama.cpp extracts it into `reasoning_content`
- `content` contains only the clean response
- This is what we WANT

**Non-Thinking Mode** (`enable_thinking: false`):
```
<|im_start|>assistant
<think>

</think>

Hello! How are you doing today? I'm here to help.
<|im_end|>
```
- Template inserts an empty `<think>\n\n</think>\n\n` pair
- Model skips reasoning entirely
- Response is immediate and clean
- Faster but potentially lower quality for complex tasks

**What we had (BROKEN — no template flag):**
```
<|im_start|>assistant
The user said "hi". I should respond...
Self-Correction on Language: checking...
Final Plan: greeting in English
Hello! How are you doing today?
<|im_end|>
```
- Model tries to reason but has no `<think>` tags
- Everything goes into `content` — reasoning AND response mixed together
- Our regex cleanup was fighting a losing battle

---

## 2. CORRECT LLAMA-SERVER FLAGS

### Deep Brain (4B) — Thinking ENABLED
```bash
llama-server \
  -m Qwen3.5-4B.Q4_K_M.gguf \
  --host 0.0.0.0 --port 8090 \
  -ngl 24 -np 1 -c 8192 \
  -fa on -ctk q4_0 -ctv q4_0 \
  --swa-full --no-mmap -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024 \
  --threads 8 --threads-batch 16
```

Key flags:
- `--jinja` — REQUIRED for Qwen3.5 chat template
- `--chat-template-kwargs '{"enable_thinking":true}'` — enables `<think>` tags
- `--reasoning-budget 1024` — caps thinking at 1024 tokens

Response format:
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "reasoning_content": "The user asked about weather. I should use the search tool...",
      "content": "Let me look that up for you! It's 22°C in Berlin right now."
    }
  }]
}
```
- `reasoning_content` → hidden from user, for debugging only
- `content` → what Pepper speaks aloud

### Fast Brain (0.8B) — Thinking DISABLED
```bash
llama-server \
  -m Qwen3.5-0.8B.Q4_K_M.gguf \
  --host 0.0.0.0 --port 8091 \
  -ngl 10 -np 1 -c 2048 \
  -fa on -ctk q4_0 -ctv q4_0 \
  -fit off \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --threads 8 --threads-batch 16
```

Key difference:
- `enable_thinking: false` — NO thinking, instant responses
- NO `--reasoning-budget` (not needed when thinking is disabled)
- Response goes straight to `content`, no `reasoning_content`

Response format:
```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Let me check that for you!"
    }
  }]
}
```
- No `reasoning_content` at all
- Clean, fast, direct responses
- Much faster: no tokens wasted on thinking

### Why This Fixes Everything
| Issue | Cause | Fix |
|---|---|---|
| Reasoning leaking into content | No `enable_thinking` flag | Add the flag |
| `</think>` tags in content | Malformed template output | Proper template kwargs |
| Empty content after thinking | All tokens spent on reasoning | Disable thinking for fast brain |
| 0.8B taking 15s for "Hi" | Wasting 256 tokens on reasoning | Disable thinking entirely |
| Inconsistent response format | Sometimes thinking, sometimes not | Explicit enable/disable per brain |

---

## 3. RECOMMENDED TEMPERATURE SETTINGS (from Qwen3.5 docs)

### Thinking Mode (4B Deep Brain)
```
temperature: 0.6
top_p: 0.95
top_k: 20
min_p: 0.0
```
- DO NOT use temperature=0 (causes endless repetitions)
- These are the official recommended settings from Qwen team

### Non-Thinking Mode (0.8B Fast Brain)
```
temperature: 0.7
top_p: 0.8
top_k: 20
min_p: 0.0
```

### General Rule
- Never use greedy decoding (temperature=0) with Qwen3.5
- Our previous `temperature=0.0` for tool calls was WRONG and caused issues
- Minimum temperature: 0.1 for structured outputs

---

## 4. MULTI-TURN CONVERSATION FORMAT

Critical from Qwen docs: **"No Thinking Content in History"**

In multi-turn conversations, previous assistant messages should contain
ONLY the final response, NOT the thinking. The Jinja template handles
this automatically, but our middleware must follow the same rule:

### CORRECT — strip thinking from history
```python
history = [
    {"role": "user", "content": "What's the weather?"},
    {"role": "assistant", "content": "It's 22°C in Berlin."},  # thinking stripped
    {"role": "user", "content": "What about tomorrow?"},
]
```

### WRONG — including thinking in history
```python
history = [
    {"role": "user", "content": "What's the weather?"},
    {"role": "assistant", "content": "<think>I need to search...</think>It's 22°C in Berlin."},
    {"role": "user", "content": "What about tomorrow?"},
]
```

Our LLMClient's `Message` class already stores only `content` (not thinking),
so the history is correctly clean. This is correct behavior.

---

## 5. TOOL CALLING — QWEN3.5 FORMAT

Qwen3.5 uses XML-based tool calls in this format:

### Defining Tools (in system prompt, handled by Jinja template)
When you pass `tools` in the API request, the Jinja template generates:
```
# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"name": "search", "description": "Search the web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}
</tools>

For each function call, return a json object with function name and
arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
```

### Model Output (tool call)
```
<tool_call>
{"name": "search", "arguments": {"query": "weather Berlin today"}}
</tool_call>
```

### Sending Tool Results Back
```json
{"role": "tool", "content": "Berlin: 22°C, partly cloudy"}
```

### How to Pass Tools via the API
```python
response = requests.post("http://localhost:8090/v1/chat/completions", json={
    "messages": messages,
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the web for current information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }
            }
        }
    ],
    "max_tokens": 1500,
    "temperature": 0.6,
})
```

llama.cpp with `--jinja` will:
1. Inject tool definitions into the system prompt automatically
2. Parse `<tool_call>` from the model output
3. Return structured `tool_calls` in the API response

---

## 6. ANTHROPIC'S APPROACH (Reference Architecture)

How Claude structures tool use — the gold standard we're adapting:

### Key Principles from Anthropic

1. **Structured Schema Definitions**
   - Every tool has a JSON schema for inputs
   - Schema validation ensures the model can't produce invalid calls
   - `strict: true` guarantees schema conformance

2. **Explicit Stop Reason**
   - `stop_reason: "end_turn"` → model finished normally
   - `stop_reason: "tool_use"` → model wants to call a tool
   - Our middleware checks this to know whether to execute tools

3. **Content Blocks (not string concatenation)**
   - Claude returns an array of content blocks, not one string
   - Each block is typed: `text`, `tool_use`, `tool_result`
   - This avoids the parsing nightmare of extracting tools from prose

4. **Agentic Loop**
   ```
   User message → Model → [text response] → done
                       → [tool_use block] → execute tool → 
                          send tool_result → Model → [text response]
   ```

5. **Tool Descriptions Matter**
   - Anthropic shows that good descriptions > good schemas
   - The description tells the model WHEN to use the tool
   - The schema tells it HOW to format the call

### Adapting This for Qwen3.5

Since Qwen3.5 uses XML tool calls (not Anthropic's JSON blocks),
our middleware translates:

```python
# Parse Qwen3.5 tool calls from response
def parse_tool_calls(content: str) -> list:
    """Extract <tool_call> blocks from model output."""
    calls = []
    for match in re.finditer(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', content, re.DOTALL):
        try:
            call = json.loads(match.group(1))
            calls.append(call)
        except json.JSONDecodeError:
            continue
    return calls

# Execute tool and format result for Qwen3.5
def format_tool_result(tool_name: str, result: str) -> dict:
    """Format tool result as a message for the conversation."""
    return {
        "role": "tool",
        "name": tool_name,
        "content": result
    }
```

---

## 7. RESPONSE PARSING — THE DEFINITIVE APPROACH

Stop regex-cleaning leaked reasoning. With proper flags, parsing is simple:

```python
def parse_response(api_response: dict) -> tuple[str, str, list]:
    """
    Parse a llama-server response into (content, thinking, tool_calls).
    
    With correct --chat-template-kwargs, the server handles all parsing.
    We just read the fields.
    """
    choice = api_response["choices"][0]
    message = choice["message"]
    
    content = message.get("content", "").strip()
    thinking = message.get("reasoning_content", "")
    
    # Tool calls (if any)
    tool_calls = message.get("tool_calls", [])
    
    # If no structured tool_calls but content has <tool_call> tags
    # (fallback for older llama.cpp versions)
    if not tool_calls and "<tool_call>" in content:
        tool_calls = parse_tool_calls(content)
        # Remove tool_call XML from spoken content
        content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
    
    return content, thinking, tool_calls
```

That's it. No 37-pattern regex. No leaked reasoning detection.
The server does the parsing when the flags are correct.

---

## 8. PRODUCTION vs DEV SETTINGS

### 6GB GPU (Production with Pepper)
```bash
# Deep Brain: all 32 layers + vision + thinking
llama-server -m Qwen3.5-4B.Q4_K_M.gguf \
  --mmproj mmproj-F16.gguf \
  -ngl 32 -c 8192 \
  --jinja --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024

# Fast Brain: all layers + NO thinking
llama-server -m Qwen3.5-0.8B.Q4_K_M.gguf \
  -ngl 99 -c 2048 \
  --jinja --chat-template-kwargs '{"enable_thinking":false}'
```

### 4GB GPU (Dev Laptop)
```bash
# Deep Brain: 24 layers + thinking
llama-server -m Qwen3.5-4B.Q4_K_M.gguf \
  -ngl 24 -c 8192 \
  --jinja --chat-template-kwargs '{"enable_thinking":true}' \
  --reasoning-budget 1024

# Fast Brain: 10 layers + NO thinking
llama-server -m Qwen3.5-0.8B.Q4_K_M.gguf \
  -ngl 10 -c 2048 \
  --jinja --chat-template-kwargs '{"enable_thinking":false}'
```

---

## 9. SUMMARY OF FIXES NEEDED

1. **Update `start_dev.sh`**: Add `--chat-template-kwargs` to both brains
2. **Update `start_production.sh`**: Same
3. **Simplify `llm_client.py`**: Remove all 37 regex patterns, use proper field parsing
4. **Update temperature profiles**: Use Qwen3.5 recommended values (0.6/0.7, never 0.0)
5. **Add tool call support**: Parse `tool_calls` from API response
6. **Update system prompts**: Use `/no_think` tag for per-message thinking control if needed
