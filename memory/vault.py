"""Obsidian Vault: read/write Pepper's memory as markdown files with [[backlinks]]."""

import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

import config


class Vault:
    """Read/write interface for Pepper's Obsidian-style brain vault."""

    def __init__(self, vault_path: str = config.BRAIN_VAULT_PATH):
        self.root = Path(vault_path)

    def read(self, relative_path: str) -> Optional[str]:
        """Read a file from the vault."""
        path = self.root / relative_path
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, relative_path: str, content: str):
        """Atomic write to vault (tmp → rename)."""
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(path)

    def append(self, relative_path: str, line: str):
        """Append a line to a vault file."""
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).exists()

    def list_files(self, directory: str, extension: str = ".md") -> List[str]:
        """List files in a vault subdirectory."""
        dir_path = self.root / directory
        if not dir_path.exists():
            return []
        return [f.name for f in dir_path.iterdir() if f.suffix == extension]

    def find_backlinks(self, target: str) -> List[str]:
        """Find all files that link to [[target]]."""
        pattern = re.compile(r'\[\[' + re.escape(target) + r'(\|[^\]]+)?\]\]')
        results = []
        for md_file in self.root.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if pattern.search(text):
                results.append(str(md_file.relative_to(self.root)))
        return results

    def search(self, query: str, directory: Optional[str] = None) -> List[Dict]:
        """Simple text search across vault files."""
        results = []
        search_root = self.root / directory if directory else self.root
        query_lower = query.lower()

        for md_file in search_root.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if query_lower in text.lower():
                results.append({
                    "path": str(md_file.relative_to(self.root)),
                    "snippet": _extract_snippet(text, query_lower),
                })
        return results


def _extract_snippet(text: str, query: str, context: int = 80) -> str:
    """Extract a short snippet around the first match."""
    idx = text.lower().find(query)
    if idx == -1:
        return text[:100]
    start = max(0, idx - context)
    end = min(len(text), idx + len(query) + context)
    return "..." + text[start:end].strip() + "..."
