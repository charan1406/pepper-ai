"""Obsidian Vault: read/write Pepper's memory as markdown files with [[backlinks]]."""

import re
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List

import config


class Vault:
    """Read/write interface for Pepper's Obsidian-style brain vault.

    Uses SQLite FTS5 as a search index alongside the .md files (source of truth).
    """

    def __init__(self, vault_path: str = config.BRAIN_VAULT_PATH):
        self.root = Path(vault_path)
        self._db = sqlite3.connect(str(self.root / ".search_index.db"))
        self._init_fts()
        self._reindex()

    def _init_fts(self):
        self._db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
                path, title, content,
                tokenize='porter unicode61'
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS vault_meta (
                path TEXT PRIMARY KEY,
                mtime REAL
            )
        """)
        self._db.commit()

    def _reindex(self):
        indexed = {}
        for row in self._db.execute("SELECT path, mtime FROM vault_meta"):
            indexed[row[0]] = row[1]

        for md_file in self.root.rglob("*.md"):
            rel = str(md_file.relative_to(self.root))
            mtime = md_file.stat().st_mtime
            if rel in indexed and indexed[rel] >= mtime:
                continue
            self._index_file(rel, md_file.read_text(encoding="utf-8"), mtime)

        current_files = {str(f.relative_to(self.root)) for f in self.root.rglob("*.md")}
        for path in set(indexed) - current_files:
            self._db.execute("DELETE FROM vault_fts WHERE path = ?", (path,))
            self._db.execute("DELETE FROM vault_meta WHERE path = ?", (path,))

        self._db.commit()

    def _index_file(self, rel_path: str, content: str, mtime: float):
        title = Path(rel_path).stem.replace("_", " ")
        self._db.execute("DELETE FROM vault_fts WHERE path = ?", (rel_path,))
        self._db.execute("DELETE FROM vault_meta WHERE path = ?", (rel_path,))
        self._db.execute(
            "INSERT INTO vault_fts (path, title, content) VALUES (?, ?, ?)",
            (rel_path, title, content)
        )
        self._db.execute(
            "INSERT INTO vault_meta (path, mtime) VALUES (?, ?)",
            (rel_path, mtime)
        )

    def read(self, relative_path: str) -> Optional[str]:
        path = self.root / relative_path
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, relative_path: str, content: str):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(path)
        self._index_file(relative_path, content, path.stat().st_mtime)
        self._db.commit()

    def append(self, relative_path: str, line: str):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        content = path.read_text(encoding="utf-8")
        self._index_file(relative_path, content, path.stat().st_mtime)
        self._db.commit()

    def exists(self, relative_path: str) -> bool:
        return (self.root / relative_path).exists()

    def list_files(self, directory: str, extension: str = ".md") -> List[str]:
        dir_path = self.root / directory
        if not dir_path.exists():
            return []
        return [f.name for f in dir_path.iterdir() if f.suffix == extension]

    def find_backlinks(self, target: str) -> List[str]:
        pattern = re.compile(r'\[\[' + re.escape(target) + r'(\|[^\]]+)?\]\]')
        results = []
        for md_file in self.root.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if pattern.search(text):
                results.append(str(md_file.relative_to(self.root)))
        return results

    def search(self, query: str, directory: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """BM25-ranked full-text search via FTS5. Falls back to substring scan on empty results."""
        fts_results = self._fts_search(query, directory, limit)
        if fts_results:
            return fts_results
        return self._substring_search(query, directory)

    def _fts_search(self, query: str, directory: Optional[str], limit: int) -> List[Dict]:
        safe_query = re.sub(r'[^\w\s]', '', query).strip()
        if not safe_query:
            return []
        fts_query = " OR ".join(safe_query.split())

        rows = self._db.execute(
            "SELECT path, snippet(vault_fts, 2, '>', '<', '...', 40), rank "
            "FROM vault_fts WHERE vault_fts MATCH ? ORDER BY rank LIMIT ?",
            (fts_query, limit)
        ).fetchall()

        results = []
        for path, snippet, _rank in rows:
            if directory and not path.startswith(directory):
                continue
            results.append({"path": path, "snippet": snippet})
        return results

    def _substring_search(self, query: str, directory: Optional[str]) -> List[Dict]:
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
    idx = text.lower().find(query)
    if idx == -1:
        return text[:100]
    start = max(0, idx - context)
    end = min(len(text), idx + len(query) + context)
    return "..." + text[start:end].strip() + "..."
