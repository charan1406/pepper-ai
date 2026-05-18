"""Pre-cached filler audio for instant playback while LLM generates."""

import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pepper.client import PepperClient


FILLER_PHRASES = {
    "en": [
        "Let me think about that.",
        "One moment please.",
        "Good question!",
        "Hmm, let me check.",
        "Sure, give me a second.",
        "Let me look into that.",
        "Interesting question!",
    ],
    "de": [
        "Moment mal, ich denke nach.",
        "Gute Frage!",
        "Einen Augenblick bitte.",
        "Hmm, lass mich nachschauen.",
        "Interessante Frage!",
    ],
}

DEFAULT_VOICE = {
    "en": "en-US-AriaNeural",
    "de": "de-DE-KatjaNeural",
}


class FillerPlayer:
    """Pre-caches filler audio at startup for instant playback."""

    def __init__(self, pepper: PepperClient, languages: Optional[list[str]] = None):
        self.pepper = pepper
        self._cache: dict[str, list[bytes]] = {}
        languages = languages or ["en"]
        for lang in languages:
            self._cache[lang] = self._render_fillers(lang)

    def play(self, language: str = "en"):
        """Play a random filler. Returns immediately after queueing."""
        clips = self._cache.get(language, self._cache.get("en", []))
        if not clips:
            self.pepper.speak("One moment.", language="en")
            return
        clip = random.choice(clips)
        self.pepper.play_audio(clip)

    def _render_fillers(self, language: str) -> list[bytes]:
        """Pre-render all filler phrases for a language via edge-tts."""
        phrases = FILLER_PHRASES.get(language, FILLER_PHRASES["en"])
        voice = DEFAULT_VOICE.get(language, DEFAULT_VOICE["en"])
        clips = []
        for phrase in phrases:
            wav = self._tts_to_wav(phrase, voice)
            if wav:
                clips.append(wav)
                print(f"[FILLER] Cached: \"{phrase}\" ({len(wav)} bytes)")
            else:
                print(f"[FILLER] WARN: Failed to render \"{phrase}\"")
        print(f"[FILLER] {len(clips)}/{len(phrases)} clips cached for '{language}'")
        return clips

    def _tts_to_wav(self, text: str, voice: str) -> Optional[bytes]:
        """Render one phrase to WAV bytes via edge-tts."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["edge-tts", "--voice", voice, "--text", text,
                 "--write-media", tmp_path],
                capture_output=True, timeout=15,
            )
            if result.returncode != 0:
                return None
            return Path(tmp_path).read_bytes()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
