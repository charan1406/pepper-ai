"""Pre-cached filler audio for instant playback while LLM generates."""

import random
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pepper.client import PepperClient
from tts.router import TTSRouter


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

    def __init__(self, pepper: PepperClient, languages: Optional[list[str]] = None,
                 tts_router: Optional[TTSRouter] = None):
        self.pepper = pepper
        self._tts = tts_router or TTSRouter(pepper)
        self._cache: dict[str, list[bytes]] = {}
        languages = languages or ["en"]
        for lang in languages:
            self._cache[lang] = self._render_fillers(lang)

    def play(self, language: str = "en"):
        clips = self._cache.get(language, self._cache.get("en", []))
        if not clips:
            self.pepper.speak("One moment.", language="en")
            return
        clip = random.choice(clips)
        self.pepper.play_audio(clip)

    def _render_fillers(self, language: str) -> list[bytes]:
        phrases = FILLER_PHRASES.get(language, FILLER_PHRASES["en"])
        clips = []
        for phrase in phrases:
            wav = self._tts.kokoro_to_wav(phrase, language)
            if not wav:
                wav = self._edge_tts_wav(phrase, language)
            if wav:
                clips.append(wav)
                print(f"[FILLER] Cached: \"{phrase}\" ({len(wav)} bytes)")
            else:
                print(f"[FILLER] WARN: Failed to render \"{phrase}\"")
        print(f"[FILLER] {len(clips)}/{len(phrases)} clips cached for '{language}'")
        return clips

    def _edge_tts_wav(self, text: str, language: str) -> Optional[bytes]:
        voice = DEFAULT_VOICE.get(language, DEFAULT_VOICE["en"])
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
