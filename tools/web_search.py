"""Web Search tool for Pepper's deep brain."""

import json
import urllib.request
import urllib.parse
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearch:
    """DuckDuckGo instant answer API — no API key needed."""

    ENDPOINT = "https://api.duckduckgo.com/"

    def __init__(self, cache_ttl: int = config.WEB_CACHE_TTL_SECONDS):
        self.cache: Dict[str, tuple] = {}  # query → (timestamp, results)
        self.cache_ttl = cache_ttl

    def search(self, query: str, max_results: int = 3) -> List[SearchResult]:
        """Search DuckDuckGo for instant answers."""
        # Check cache
        if query in self.cache:
            ts, results = self.cache[query]
            if time.time() - ts < self.cache_ttl:
                return results

        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        })
        url = f"{self.ENDPOINT}?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PepperBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        results = []

        # Abstract (main answer)
        if data.get("Abstract"):
            results.append(SearchResult(
                title=data.get("Heading", query),
                url=data.get("AbstractURL", ""),
                snippet=data["Abstract"][:300],
            ))

        # Related topics
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(SearchResult(
                    title=topic.get("Text", "")[:80],
                    url=topic.get("FirstURL", ""),
                    snippet=topic.get("Text", "")[:200],
                ))

        results = results[:max_results]
        self.cache[query] = (time.time(), results)
        return results

    def format_for_llm(self, results: List[SearchResult]) -> str:
        """Format search results as text for LLM context injection."""
        if not results:
            return "No search results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}")
            lines.append(f"   {r.snippet}")
        return "\n".join(lines)

    def tool_definition(self) -> Dict:
        """OpenAI-format tool definition for LLM tool calling."""
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information. Use when you don't know something or need up-to-date facts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
