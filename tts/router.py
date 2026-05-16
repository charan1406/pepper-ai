"""TTS Router: picks the best TTS engine for the language/situation.

Priority:
  1. Pepper native TTS (low latency, ~18 languages)
  2. Edge TTS (high quality, needs internet, any language)
  3. Piper TTS (offline, fast, limited voices) — future

For now: Pepper native for supported languages, edge-tts for others.
"""

import subprocess
import tempfile
import base64
from typing import Optional
from pathlib import Path

import config
from pepper.client import PepperClient


class TTSRouter:
    """Routes TTS to the best available engine."""

    def __init__(self, pepper: PepperClient):
        self.pepper = pepper
        self.native_languages = set(config.PEPPER_NATIVE_TTS_LANGUAGES)

    def speak(self, text: str, language: str = "en") -> bool:
        """Speak text using the best available TTS."""
        if not text.strip():
            return False

        if language in self.native_languages:
            return self.pepper.speak(text, language=language)

        # Fall back to edge-tts for unsupported languages
        if config.EDGE_TTS_ENABLED:
            return self._edge_tts(text, language)

        # Last resort: Pepper native with 'en'
        return self.pepper.speak(text, language="en")

    def _edge_tts(self, text: str, language: str) -> bool:
        """Use edge-tts to generate audio and play via Pepper."""
        voice = self._pick_voice(language)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["edge-tts", "--voice", voice, "--text", text, "--write-media", tmp_path],
                capture_output=True, timeout=15
            )
            if result.returncode != 0:
                return False

            wav_bytes = Path(tmp_path).read_bytes()
            return self.pepper.play_audio(wav_bytes)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _pick_voice(self, language: str) -> str:
        """Pick edge-tts voice for a language."""
        if language == "ta":
            return config.EDGE_TTS_VOICE_TAMIL
        return config.EDGE_TTS_VOICE_DEFAULT
