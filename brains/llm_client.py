"""
LLM Client — Brain Interface (v4)
=========================================
Based on official Qwen3.5 documentation + JARVIS audit findings.

Critical: Qwen3.5 requires `chat_template_kwargs: {"enable_thinking": bool}`
passed PER-REQUEST in the API body, not just as a server flag.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Generator

import httpx


# ─── Sampling Profiles (from Qwen3.5 official docs) ─────────────
# Source: https://huggingface.co/Qwen/Qwen3.5-4B
#
# CRITICAL: Qwen3.5 requires top_k=20 and presence_penalty=1.5 for
# general tasks. Temperature=0.0 causes infinite loops — minimum 0.1.

TEMP_PROFILES = {
    # Thinking mode — general tasks
    "think_general": {
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.5,
    },
    # Thinking mode — precise coding
    "think_code": {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 0.0,
    },
    # Non-thinking — general tasks
    "instruct_general": {
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 1.5,
    },
    # Non-thinking — reasoning tasks
    "instruct_reasoning": {
        "temperature": 1.0,
        "top_p": 1.0,
        "top_k": 40,
        "min_p": 0.0,
        "presence_penalty": 2.0,
    },
    # Structured output (JSON, tool calls) — low but never 0
    "structured": {
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 20,
        "min_p": 0.0,
        "presence_penalty": 0.0,
    },

    # ─── Aliases for the orchestrator ────────────────────────
    "factual":  None,   # → resolved based on thinking mode
    "social":   None,
    "filler":   None,
    "vision":   None,
    "tool":     None,   # → structured
    "creative": None,
    "default":  None,
}

def resolve_profile(profile: str, thinking_enabled: bool) -> Dict:
    """Resolve a profile name to actual sampling params."""
    direct = {
        "think_general", "think_code",
        "instruct_general", "instruct_reasoning", "structured"
    }
    if profile in direct:
        return TEMP_PROFILES[profile]

    # Resolve aliases based on whether thinking is enabled
    if thinking_enabled:
        mapping = {
            "factual": "think_general",
            "social": "think_general",
            "vision": "think_general",
            "creative": "think_general",
            "default": "think_general",
            "filler": "think_general",
            "tool": "structured",
        }
    else:
        mapping = {
            "factual": "instruct_general",
            "social": "instruct_general",
            "vision": "instruct_general",
            "creative": "instruct_general",
            "default": "instruct_general",
            "filler": "instruct_general",
            "tool": "structured",
        }

    resolved = mapping.get(profile, "instruct_general" if not thinking_enabled else "think_general")
    return TEMP_PROFILES[resolved]


@dataclass
class LLMResponse:
    """Structured response from an LLM call."""
    content: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    escalated: bool = False
    finish_reason: str = ""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tok_per_sec: float = 0
    prompt_ms: float = 0
    wall_time: float = 0
    model: str = ""
    success: bool = True
    error: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.content.strip()

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def _extract_from_thinking(self) -> str:
        """When content is empty, try to extract the final answer from thinking."""
        if not self.thinking:
            return ""
        # The final answer is usually the last non-empty paragraph
        paragraphs = [p.strip() for p in self.thinking.split('\n\n') if p.strip()]
        if not paragraphs:
            return ""
        # Walk backwards to find something that looks like a response (not reasoning)
        for para in reversed(paragraphs):
            lines = para.strip().split('\n')
            last = lines[-1].strip()
            if re.match(r'^(Thinking|Step|Note|Correction|Draft|Plan|Analysis)', last, re.I):
                continue
            if re.match(r'^\d+\.\s+\*\*', last):
                continue
            # Found something that looks like actual output
            return last
        return ""

    @property
    def spoken_text(self) -> str:
        """Clean text for Pepper's TTS. Max 3 sentences."""
        text = self.content.strip()
        # Strip think tags (closed and unclosed) — JARVIS pattern
        text = re.sub(r'<think>[\s\S]*?</think>\s*', '', text).strip()
        text = re.sub(r'<think>[\s\S]*$', '', text).strip()
        text = re.sub(r'</?think>', '', text).strip()
        # Thinking-eats-content fallback: extract answer after </think> in reasoning
        if not text and self.thinking:
            after = self.thinking.split('</think>')[-1].strip() if '</think>' in self.thinking else ""
            if after:
                text = re.sub(r'</?think>', '', after).strip()
            if not text:
                text = self._extract_from_thinking()
        # Remove markdown
        for char in ["*", "#", "`", "~"]:
            text = text.replace(char, "")
        # Remove leaked reasoning patterns (safety net for small models)
        lines = text.split('\n')
        clean = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if re.match(r'^\d+\.\s+\w', s): continue
            if re.match(r'^(Correction|Refining|Checking|Draft|Note|Step|Plan|Recall|Identify)', s, re.I): continue
            if re.match(r'^(Self-Correction|Final Plan|Revised Draft|Thinking Process|Output|Language:|Content:|Constraint)', s, re.I): continue
            if re.match(r'^(Looking at|Or shorter|Proceeding|Response Plan|Analysis|Reasoning)', s, re.I): continue
            clean.append(line)
        text = '\n'.join(clean).strip()
        # Remove leading colon artifacts
        text = re.sub(r'^:\s*', '', text).strip()
        # Keep max 3 sentences
        if text:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            text = ' '.join(sentences[:3]).strip()
        return text


@dataclass
class Message:
    """A conversation message. Only stores content (never thinking)."""
    role: str
    content: str

    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}


def _parse_tool_calls_xml(content: str) -> tuple:
    """Extract Qwen3.5 <tool_call> blocks from content."""
    tool_calls = []
    for match in re.finditer(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', content, re.DOTALL):
        try:
            tool_calls.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    if tool_calls:
        clean = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.DOTALL).strip()
        return clean, tool_calls
    return content, []


class LLMClient:
    """
    Client for one llama-server instance.
    
    Args:
        base_url: llama-server URL (e.g. http://localhost:8090/v1)
        name: "deep" or "fast" — determines default thinking behavior
        thinking: Whether this brain uses thinking mode
        default_max_tokens: Default max tokens per request
    """

    ESCALATE_KEYWORD = "ESCALATE"

    def __init__(self, base_url: str = "http://localhost:8090/v1",
                 name: str = "deep",
                 thinking: bool = True,
                 default_max_tokens: int = 4096,
                 timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.thinking = thinking
        self.default_max_tokens = default_max_tokens
        self.timeout = timeout
        self._http = httpx.Client(timeout=httpx.Timeout(timeout, connect=10))

    # ─── Core API Call ───────────────────────────────────────────

    def _build_payload(self, messages: List[Dict], max_tokens: int,
                       tools: Optional[List[Dict]] = None,
                       **sampling_params) -> Dict:
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {
                "enable_thinking": self.thinking
            },
        }
        payload.update(sampling_params)
        if tools:
            payload["tools"] = tools
        return payload

    def _parse_result(self, result: Dict, wall_time: float) -> LLMResponse:
        choice = result.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage = result.get("usage", {})
        timings = result.get("timings", {})

        content = msg.get("content", "") or ""
        thinking = msg.get("reasoning_content", "") or ""

        tool_calls = []
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                tool_calls.append({
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", {}),
                })
        elif "<tool_call>" in content:
            content, tool_calls = _parse_tool_calls_xml(content)

        content = re.sub(r'</?think>', '', content).strip()
        escalated = content.strip().upper() == self.ESCALATE_KEYWORD

        return LLMResponse(
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            escalated=escalated,
            finish_reason=choice.get("finish_reason", ""),
            total_tokens=usage.get("total_tokens", 0),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            tok_per_sec=timings.get("predicted_per_second", 0),
            prompt_ms=timings.get("prompt_ms", 0),
            wall_time=wall_time,
            model=result.get("model", ""),
            success=True,
        )

    def _call(self, messages: List[Dict], max_tokens: int,
              tools: Optional[List[Dict]] = None,
              **sampling_params) -> LLMResponse:
        """Make a raw API call to the llama-server."""
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(messages, max_tokens, tools, **sampling_params)

        t0 = time.time()
        try:
            resp = self._http.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
        except httpx.ConnectError as e:
            return LLMResponse(
                success=False,
                error=f"Connection to {self.name} brain failed: {e}",
                wall_time=time.time() - t0,
            )
        except Exception as e:
            return LLMResponse(
                success=False, error=str(e),
                wall_time=time.time() - t0,
            )

        return self._parse_result(result, time.time() - t0)

    def _call_stream(self, messages: List[Dict], max_tokens: int,
                     tools: Optional[List[Dict]] = None,
                     **sampling_params) -> Generator[str, None, LLMResponse]:
        """Streaming call — yields content tokens as they arrive, returns full LLMResponse."""
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(messages, max_tokens, tools, **sampling_params)
        payload["stream"] = True

        t0 = time.time()
        content_parts = []
        thinking_parts = []
        finish_reason = ""
        model = ""

        try:
            with self._http.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    model = model or chunk.get("model", "")
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    finish_reason = chunk.get("choices", [{}])[0].get("finish_reason") or finish_reason

                    if delta.get("reasoning_content"):
                        thinking_parts.append(delta["reasoning_content"])
                    if delta.get("content"):
                        token = delta["content"]
                        content_parts.append(token)
                        yield token
        except Exception as e:
            return LLMResponse(success=False, error=str(e), wall_time=time.time() - t0)

        wall_time = time.time() - t0
        content = "".join(content_parts)
        thinking = "".join(thinking_parts)

        tool_calls = []
        if "<tool_call>" in content:
            content, tool_calls = _parse_tool_calls_xml(content)
        content = re.sub(r'</?think>', '', content).strip()

        return LLMResponse(
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            escalated=content.strip().upper() == self.ESCALATE_KEYWORD,
            finish_reason=finish_reason,
            wall_time=wall_time,
            model=model,
            success=True,
        )

    # ─── High-Level Methods ──────────────────────────────────────

    def chat(self, user_message: str,
             system: Optional[str] = None,
             history: Optional[List[Message]] = None,
             profile: str = "default",
             max_tokens: Optional[int] = None,
             tools: Optional[List[Dict]] = None,
             **kwargs) -> LLMResponse:
        """Send a chat message and get a response."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            for msg in history:
                messages.append(msg.to_dict())
        messages.append({"role": "user", "content": user_message})

        sampling = resolve_profile(profile, self.thinking)
        params = {**sampling, **kwargs}

        return self._call(
            messages,
            max_tokens or self.default_max_tokens,
            tools=tools,
            **params
        )

    def deep_query(self, user_message: str,
                   system: str,
                   person_memory: Optional[str] = None,
                   scene: Optional[str] = None,
                   search_results: Optional[str] = None,
                   history: Optional[List[Message]] = None,
                   tools: Optional[List[Dict]] = None,
                   profile: str = "default",
                   max_tokens: int = 4096) -> LLMResponse:
        """Full deep brain query with context blocks."""
        parts = []
        if scene:
            parts.append(f"[SCENE]\n{scene}")
        if person_memory:
            parts.append(f"[PERSON MEMORY]\n{person_memory}")
        if search_results:
            parts.append(f"[SEARCH RESULTS]\n{search_results}")
        parts.append(f"[USER]\n{user_message}")

        return self.chat(
            "\n\n".join(parts),
            system=system, history=history,
            profile=profile, max_tokens=max_tokens,
            tools=tools,
        )

    def generate_json(self, prompt: str, system: str,
                      max_tokens: int = 1000) -> Optional[Dict]:
        """Generate structured JSON output."""
        system_json = system + "\n\nRespond with valid JSON only. No markdown."
        resp = self.chat(prompt, system=system_json, profile="tool", max_tokens=max_tokens)

        if not resp.success:
            return None

        text = resp.content.strip()
        if not text:
            return None

        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # ─── Health ──────────────────────────────────────────────────

    def is_alive(self) -> bool:
        url = self.base_url.replace("/v1", "") + "/health"
        try:
            resp = self._http.get(url, timeout=5)
            return resp.json().get("status") == "ok"
        except Exception:
            return False

    def __repr__(self):
        return f"LLMClient(name={self.name}, thinking={self.thinking}, url={self.base_url})"
