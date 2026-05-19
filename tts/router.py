"""TTS Router: picks the best TTS engine for the language/situation.

Priority for real-time speech:
  1. Pepper native TTS (low latency, ~18 languages)
  2. Edge TTS (high quality, needs internet, any language)

Kokoro-82M is used for offline filler pre-caching (high quality but ~3.6x RTF on CPU).
"""

import io
import subprocess
import tempfile
from typing import Optional
from pathlib import Path

import config
from pepper.client import PepperClient

KOKORO_LANG_MAP = {
    "en": "en-us", "de": "de", "es": "es", "fr": "fr",
    "ja": "ja", "ko": "ko", "zh": "cmn",
}

KOKORO_VOICE_MAP = {
    "en": "af_heart", "de": "af_heart", "es": "ef_dora", "fr": "ff_siwis",
    "ja": "jf_alpha", "ko": "af_heart", "zh": "zf_xiaobei",
}


class TTSRouter:
    """Routes TTS to the best available engine.

    On 6GB prod (KOKORO_GPU=true): Kokoro on GPU for all TTS, fully offline.
    On 4GB dev: Kokoro on CPU for filler pre-caching, Pepper native / edge-tts for live.
    """

    def __init__(self, pepper: PepperClient):
        self.pepper = pepper
        self.native_languages = set(config.PEPPER_NATIVE_TTS_LANGUAGES)
        self.gpu_mode = config.KOKORO_GPU
        self._kokoro = None
        self._kokoro_checked = False

    def _get_kokoro(self):
        if self._kokoro_checked:
            return self._kokoro
        self._kokoro_checked = True
        model_path = config.KOKORO_MODEL_ONNX
        voices_path = config.KOKORO_VOICES_BIN
        if not (Path(model_path).exists() and Path(voices_path).exists()):
            print("[TTS] Kokoro model files not found, skipping")
            return None
        try:
            from kokoro_onnx import Kokoro
            if self.gpu_mode:
                import onnxruntime
                providers = onnxruntime.get_available_providers()
                if "CUDAExecutionProvider" in providers:
                    session_options = onnxruntime.SessionOptions()
                    session = onnxruntime.InferenceSession(
                        model_path, session_options,
                        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                    )
                    self._kokoro = Kokoro.from_session(session, voices_path)
                    print("[TTS] Kokoro-82M loaded (GPU — CUDA)")
                else:
                    self._kokoro = Kokoro(model_path, voices_path)
                    print("[TTS] Kokoro-82M loaded (CPU fallback — no CUDA provider)")
            else:
                self._kokoro = Kokoro(model_path, voices_path)
                print("[TTS] Kokoro-82M loaded (CPU)")
        except Exception as e:
            print(f"[TTS] Kokoro unavailable: {e}")
        return self._kokoro

    def speak(self, text: str, language: str = "en") -> bool:
        if not text.strip():
            return False

        if self.gpu_mode:
            wav = self.kokoro_to_wav(text, language)
            if wav:
                return self.pepper.play_audio(wav)

        if language in self.native_languages:
            return self.pepper.speak(text, language=language)

        if config.EDGE_TTS_ENABLED:
            return self._edge_tts(text, language)

        return self.pepper.speak(text, language="en")

    def kokoro_to_wav(self, text: str, language: str = "en") -> Optional[bytes]:
        """Render text to WAV bytes via Kokoro."""
        kokoro = self._get_kokoro()
        if not kokoro:
            return None

        lang = KOKORO_LANG_MAP.get(language, "en-us")
        voice = KOKORO_VOICE_MAP.get(language, "af_heart")
        try:
            import soundfile as sf
            samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0, lang=lang)
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV")
            return buf.getvalue()
        except Exception:
            return None

    def _edge_tts(self, text: str, language: str) -> bool:
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
        if language == "ta":
            return config.EDGE_TTS_VOICE_TAMIL
        return config.EDGE_TTS_VOICE_DEFAULT
