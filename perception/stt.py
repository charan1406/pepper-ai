"""Speech-to-Text: faster-whisper + Silero VAD"""

import io
import wave
import base64
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass

import numpy as np
import torch
from faster_whisper import WhisperModel

import config


@dataclass
class TranscriptResult:
    text: str
    language: str
    confidence: float
    duration: float


class SpeechToText:
    def __init__(self,
                 model_size: str = config.WHISPER_MODEL,
                 device: str = config.WHISPER_DEVICE,
                 compute_type: str = config.WHISPER_COMPUTE_TYPE,
                 vad_threshold: float = config.VAD_THRESHOLD,
                 energy_threshold: float = config.AUDIO_ENERGY_THRESHOLD,
                 silence_timeout: float = config.SILENCE_TIMEOUT_MS / 1000,
                 min_speech_duration: float = config.MIN_SPEECH_DURATION_MS / 1000,
                 isolator=None):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.vad_threshold = vad_threshold
        self.energy_threshold = energy_threshold
        self.silence_timeout = silence_timeout
        self.min_speech_duration = min_speech_duration
        self.isolator = isolator

        self.vad_model, self.vad_utils = torch.hub.load(
            'snakers4/silero-vad', 'silero_vad', trust_repo=True
        )
        self.get_speech_timestamps = self.vad_utils[0]

    def _decode_wav(self, wav_b64: str) -> np.ndarray:
        """Decode base64 WAV to 16kHz float32 numpy array."""
        wav_bytes = base64.b64decode(wav_b64)

        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                sample_rate = wf.getframerate()
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        if sample_rate != 16000:
            import torchaudio
            audio_tensor = torch.from_numpy(audio).unsqueeze(0)
            audio_tensor = torchaudio.functional.resample(audio_tensor, sample_rate, 16000)
            audio = audio_tensor.squeeze(0).numpy()

        return audio

    def transcribe_wav_bytes(self, wav_b64: str,
                             person_id: Optional[str] = None) -> Optional[TranscriptResult]:
        """Transcribe base64 WAV audio. Returns None if no speech detected."""
        audio = self._decode_wav(wav_b64)

        # Speaker isolation: denoise + extract target speaker
        if self.isolator is not None:
            audio = self.isolator.isolate(audio, person_id=person_id)

        # Energy gate — reject low-energy audio to prevent Whisper hallucinations
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < self.energy_threshold:
            return None

        # VAD check
        audio_tensor = torch.from_numpy(audio)
        speech_timestamps = self.get_speech_timestamps(
            audio_tensor, self.vad_model,
            threshold=self.vad_threshold,
            min_speech_duration_ms=int(self.min_speech_duration * 1000),
            sampling_rate=16000
        )
        if not speech_timestamps:
            return None

        # Transcribe
        segments, info = self.model.transcribe(audio, language=None)
        text = " ".join(seg.text for seg in segments).strip()

        if not text:
            return None

        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=info.language_probability,
            duration=len(audio) / 16000
        )

    def listen_loop(self, pepper_client, callback: Callable[[TranscriptResult], None],
                    record_seconds: float = 5.0, stop_event: threading.Event = None):
        """Continuous listening loop — records chunks from bridge and transcribes."""
        if stop_event is None:
            stop_event = threading.Event()

        while not stop_event.is_set():
            wav_b64 = pepper_client.record_audio(seconds=record_seconds)
            if wav_b64 is None:
                time.sleep(0.5)
                continue

            result = self.transcribe_wav_bytes(wav_b64)
            if result and result.text.strip():
                callback(result)
