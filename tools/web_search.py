"""Web Search tool for Pepper's deep brain — SearXNG backend."""

import json
import urllib.request
import urllib.parse
import time
from typing import List, Dict
from dataclasses import dataclass

import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class WebSearch:
    """SearXNG search — self-hosted, unlimited, real web results."""

    def __init__(self, cache_ttl: int = config.WEB_CACHE_TTL_SECONDS):
        self.endpoint = config.SEARX_URL
        self.cache: Dict[str, tuple] = {}
        self.cache_ttl = cache_ttl

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        if query in self.cache:
            ts, results = self.cache[query]
            if time.time() - ts < self.cache_ttl:
                return results

        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "categories": "general",
        })
        url = f"{self.endpoint}?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PepperBot/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        results = []
        for r in data.get("results", [])[:max_results]:
            results.append(SearchResult(
                title=r.get("title", "(no title)"),
                url=r.get("url", ""),
                snippet=r.get("content", "")[:300],
            ))

        self.cache[query] = (time.time(), results)
        return results

    def format_for_llm(self, results: List[SearchResult]) -> str:
        if not results:
            return "No search results found."
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}")
            if r.snippet:
                lines.append(f"   {r.snippet}")
            lines.append(f"   {r.url}")
            lines.append("")
        return "\n".join(lines)

    def tool_definition(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information. Use when you need up-to-date facts, news, prices, people, events, or anything that may have changed recently.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query — short and specific, 2-6 words"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
