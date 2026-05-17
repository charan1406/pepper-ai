"""
LLM Client — Dual Brain Interface (v3)
=========================================
Based on official Qwen3.5 documentation + JARVIS audit findings.

Critical: Qwen3.5 requires `chat_template_kwargs: {"enable_thinking": bool}`
passed PER-REQUEST in the API body, not just as a server flag.

Deep Brain (4B): enable_thinking=True → reasoning in `reasoning_content`
Fast Brain (0.8B): enable_thinking=False → direct response, no thinking overhead
"""

import json
import re
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


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
    "factual":  None,   # → think_general (deep brain)
    "social":   None,   # → instruct_general (fast brain)
    "filler":   None,   # → instruct_general (fast brain)
    "vision":   None,   # → think_general (deep brain)
    "tool":     None,   # → structured
    "creative": None,   # → instruct_general
    "default":  None,   # → resolved based on brain type
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

    @property
    def spoken_text(self) -> str:
        """Clean text for Pepper's TTS. Max 3 sentences."""
        text = self.content.strip()
        if not text:
            return ""
        # Remove think tag blocks and stray tags
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        text = re.sub(r'</?think>', '', text).strip()
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

    # ─── Core API Call ───────────────────────────────────────────

    def _call(self, messages: List[Dict], max_tokens: int,
              tools: Optional[List[Dict]] = None,
              **sampling_params) -> LLMResponse:
        """Make a raw API call to the llama-server."""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            # CRITICAL: pass enable_thinking per-request
            "chat_template_kwargs": {
                "enable_thinking": self.thinking
            },
        }
        payload.update(sampling_params)

        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
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

        wall_time = time.time() - t0

        # Parse response
        choice = result.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage = result.get("usage", {})
        timings = result.get("timings", {})

        content = msg.get("content", "") or ""
        thinking = msg.get("reasoning_content", "") or ""

        # Parse tool calls
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

        # Clean stray think tags from content
        content = re.sub(r'</?think>', '', content).strip()

        # ESCALATE check
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

    def generate_filler(self, user_message: str,
                        person_name: Optional[str] = None,
                        language: str = "en") -> LLMResponse:
        """Generate a quick filler (fast brain, thinking=OFF)."""
        system = (
            "You are Pepper, a friendly robot. Generate ONE short sentence to "
            "acknowledge what the user said. Do NOT answer the question. "
            "Just a brief filler like 'Let me check!' or 'Good question, one moment!' "
            f"Respond in language: {language}. "
            "Output ONLY the filler sentence."
        )
        if person_name:
            system += f" The person's name is {person_name}."

        return self.chat(user_message, system=system, profile="filler", max_tokens=100)

    def respond_social(self, user_message: str,
                       person_name: Optional[str] = None,
                       language: str = "en") -> LLMResponse:
        """Direct social response (fast brain, thinking=OFF)."""
        system = (
            "You are Pepper, a friendly robot. Respond in 1-2 sentences. "
            "If you cannot answer confidently, respond with ONLY: ESCALATE\n"
            f"Respond in language: {language}."
        )
        prompt = user_message
        if person_name:
            prompt = f"(Person: {person_name}) {user_message}"

        return self.chat(prompt, system=system, profile="social", max_tokens=200)

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
            with urllib.request.urlopen(urllib.request.Request(url), timeout=5) as resp:
                return json.loads(resp.read()).get("status") == "ok"
        except Exception:
            return False

    def __repr__(self):
        return f"LLMClient(name={self.name}, thinking={self.thinking}, url={self.base_url})"
