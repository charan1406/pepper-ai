"""Person Memory: CRUD for person files in the Obsidian vault."""

import re
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path

from memory.vault import Vault
import config


class PersonMemory:
    """Manages person markdown files with frontmatter and [[backlinks]]."""

    def __init__(self, vault: Optional[Vault] = None):
        self.vault = vault or Vault()
        self.people_dir = "people"

    def get(self, person_id: str) -> Optional[str]:
        """Get full person file content."""
        return self.vault.read(f"{self.people_dir}/{person_id}.md")

    def get_quick_context(self, person_id: str) -> Optional[str]:
        """Get just the Quick Context section for LLM prompt injection."""
        content = self.get(person_id)
        if not content:
            return None

        # Extract frontmatter fields
        name = _extract_frontmatter(content, "name") or person_id
        lang = _extract_frontmatter(content, "language") or "en"
        greeting = _extract_frontmatter(content, "greeting_style") or "informal"
        interactions = _extract_frontmatter(content, "total_interactions") or "0"

        # Extract Quick Context section
        quick = _extract_section(content, "Quick Context")

        lines = [
            f"Name: {name}",
            f"Language: {lang}",
            f"Greeting: {greeting}",
            f"Interactions: {interactions}",
        ]
        if quick:
            lines.append(quick)
        return "\n".join(lines)

    def exists(self, person_id: str) -> bool:
        return self.vault.exists(f"{self.people_dir}/{person_id}.md")

    def create(self, person_id: str, name: str, language: str = "en") -> str:
        """Create a new person file from template."""
        template = self.vault.read(f"{self.people_dir}/_template.md") or ""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        content = template.replace("{name}", name)
        content = _set_frontmatter(content, "id", person_id)
        content = _set_frontmatter(content, "name", name)
        content = _set_frontmatter(content, "language", language)
        content = _set_frontmatter(content, "first_seen", now)
        content = _set_frontmatter(content, "last_seen", now)

        self.vault.write(f"{self.people_dir}/{person_id}.md", content)
        return content

    def update_last_seen(self, person_id: str):
        """Update last_seen timestamp and increment interaction count."""
        content = self.get(person_id)
        if not content:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        content = _set_frontmatter(content, "last_seen", now)

        count = int(_extract_frontmatter(content, "total_interactions") or "0")
        content = _set_frontmatter(content, "total_interactions", str(count + 1))

        self.vault.write(f"{self.people_dir}/{person_id}.md", content)

    def add_context(self, person_id: str, fact: str):
        """Add a fact to the Quick Context section."""
        content = self.get(person_id)
        if not content:
            return

        marker = "## Quick Context"
        if marker in content:
            idx = content.index(marker) + len(marker)
            next_section = content.find("\n## ", idx)
            if next_section == -1:
                next_section = len(content)

            existing = content[idx:next_section].strip()
            lines = [l for l in existing.split("\n") if l.strip() and "no context yet" not in l.lower()]
            lines.append(f"- {fact}")

            # Keep max items
            lines = lines[-config.MAX_QUICK_CONTEXT_ITEMS:]

            new_section = marker + "\n" + "\n".join(lines) + "\n"
            content = content[:content.index(marker)] + new_section + content[next_section:]
            self.vault.write(f"{self.people_dir}/{person_id}.md", content)

    def log_conversation(self, person_id: str, user_text: str, pepper_text: str):
        """Append to Recent Conversations section."""
        content = self.get(person_id)
        if not content:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n### {now}\n- User: {user_text}\n- Pepper: {pepper_text}\n"

        marker = "## Recent Conversations"
        if marker in content:
            idx = content.index(marker) + len(marker)
            content = content[:idx] + entry + content[idx:]
            self.vault.write(f"{self.people_dir}/{person_id}.md", content)

    def list_people(self) -> list:
        """List all person IDs."""
        files = self.vault.list_files(self.people_dir)
        return [f[:-3] for f in files if f != "_template.md" and f.endswith(".md")]

    def id_from_name(self, name: str) -> str:
        """Convert display name to file-safe ID."""
        return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def _extract_frontmatter(content: str, key: str) -> Optional[str]:
    match = re.search(rf'^{key}:\s*(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else None


def _set_frontmatter(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf'^({key}:\s*)(.*)$', re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(rf'\g<1>{value}', content)
    # Insert before closing ---
    return content.replace("---\n\n", f"{key}: {value}\n---\n\n", 1)


def _extract_section(content: str, heading: str) -> Optional[str]:
    pattern = re.compile(rf'^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)', re.MULTILINE | re.DOTALL)
    match = pattern.search(content)
    if match:
        text = match.group(1).strip()
        if text and "no context yet" not in text.lower():
            return text
    return None
