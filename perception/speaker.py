"""Speaker Isolation: DeepFilterNet denoise + Resemblyzer target speaker extraction.

Pipeline: denoise → extract enrolled speaker (or loudest) → return cleaned audio.
Runs on CPU. Adds ~130ms to the STT pipeline (80ms denoise + 50ms extraction).
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List

import config


class SpeakerIsolator:
    """Isolates target speaker from noisy multi-speaker audio."""

    def __init__(self,
                 enrollment_dir: str = config.VOICE_ENCODINGS_DIR,
                 similarity_threshold: float = config.SPEAKER_SIMILARITY_THRESHOLD):
        self.enrollment_dir = Path(enrollment_dir)
        self.enrollment_dir.mkdir(parents=True, exist_ok=True)
        self.similarity_threshold = similarity_threshold

        self._df_model = None
        self._df_state = None
        self._encoder = None
        self._known_embeddings: dict[str, np.ndarray] = {}

        self._init_deepfilter()
        self._init_resemblyzer()
        self._load_enrollments()

    def _init_deepfilter(self):
        try:
            self._patch_torchaudio()
            from df.enhance import init_df
            self._df_model, self._df_state, _ = init_df()
            print("[SPEAKER] DeepFilterNet loaded")
        except Exception as e:
            print(f"[SPEAKER] DeepFilterNet unavailable: {e}")

    @staticmethod
    def _patch_torchaudio():
        """Shim for torchaudio.backend.common.AudioMetaData removed in torchaudio 2.11+."""
        import sys
        if "torchaudio.backend.common" in sys.modules:
            return
        try:
            from torchaudio.backend.common import AudioMetaData  # noqa: F401
        except (ImportError, ModuleNotFoundError):
            import types
            from dataclasses import dataclass

            @dataclass
            class AudioMetaData:
                sample_rate: int = 0
                num_channels: int = 0
                num_frames: int = 0

            backend_common = types.ModuleType("torchaudio.backend.common")
            backend_common.AudioMetaData = AudioMetaData
            backend = types.ModuleType("torchaudio.backend")
            backend.common = backend_common
            sys.modules["torchaudio.backend"] = backend
            sys.modules["torchaudio.backend.common"] = backend_common

    def _init_resemblyzer(self):
        try:
            from resemblyzer import VoiceEncoder
            self._encoder = VoiceEncoder("cpu")
            print("[SPEAKER] Resemblyzer encoder loaded")
        except Exception as e:
            print(f"[SPEAKER] Resemblyzer unavailable: {e}")

    def _load_enrollments(self):
        for npy_file in self.enrollment_dir.glob("*.npy"):
            name = npy_file.stem
            self._known_embeddings[name] = np.load(npy_file)
        if self._known_embeddings:
            print(f"[SPEAKER] Loaded {len(self._known_embeddings)} voice enrollment(s)")

    def denoise(self, audio_16k: np.ndarray) -> np.ndarray:
        """Remove background noise via DeepFilterNet. Returns cleaned 16kHz audio."""
        if self._df_model is None:
            return audio_16k

        try:
            import torch
            import torchaudio
            from df.enhance import enhance

            t = torch.from_numpy(audio_16k).unsqueeze(0).float()
            # DeepFilterNet expects 48kHz
            t_48k = torchaudio.functional.resample(t, 16000, 48000)
            enhanced = enhance(self._df_model, self._df_state, t_48k)
            # Back to 16kHz
            t_16k = torchaudio.functional.resample(enhanced, 48000, 16000)
            return t_16k.squeeze(0).numpy()
        except Exception:
            return audio_16k

    def _get_embedding(self, audio_16k: np.ndarray) -> Optional[np.ndarray]:
        """Extract voice embedding from audio."""
        if self._encoder is None:
            return None
        try:
            from resemblyzer import preprocess_wav
            processed = preprocess_wav(audio_16k, source_sr=16000)
            if len(processed) < 1600:
                return None
            return self._encoder.embed_utterance(processed)
        except Exception:
            return None

    def identify_speaker(self, audio_16k: np.ndarray) -> Tuple[str, float]:
        """Match audio against enrolled voices. Returns (name, similarity)."""
        embedding = self._get_embedding(audio_16k)
        if embedding is None:
            return "unknown", 0.0

        best_name = "unknown"
        best_sim = 0.0

        for name, enrolled_emb in self._known_embeddings.items():
            sim = np.dot(embedding, enrolled_emb) / (
                np.linalg.norm(embedding) * np.linalg.norm(enrolled_emb) + 1e-8
            )
            if sim > best_sim:
                best_sim = float(sim)
                best_name = name

        if best_sim < self.similarity_threshold:
            return "unknown", best_sim

        return best_name, best_sim

    def extract_speaker(self, audio_16k: np.ndarray, speaker_id: str) -> np.ndarray:
        """Extract a specific enrolled speaker via spectral masking."""
        if self._encoder is None or speaker_id not in self._known_embeddings:
            return audio_16k

        try:
            from resemblyzer import preprocess_wav
            target_emb = self._known_embeddings[speaker_id]

            processed = preprocess_wav(audio_16k, source_sr=16000)
            if len(processed) < 1600:
                return audio_16k

            # Compute similarity over sliding windows
            window_len = int(1.6 * 16000)  # 1.6s windows
            hop_len = int(0.4 * 16000)     # 0.4s hop
            n_samples = len(processed)

            if n_samples < window_len:
                emb = self._encoder.embed_utterance(processed)
                sim = float(np.dot(emb, target_emb) / (
                    np.linalg.norm(emb) * np.linalg.norm(target_emb) + 1e-8
                ))
                return audio_16k if sim >= self.similarity_threshold else audio_16k * 0.0

            # Build per-sample mask from windowed similarity
            mask = np.zeros(n_samples, dtype=np.float32)
            counts = np.zeros(n_samples, dtype=np.float32)

            for start in range(0, n_samples - window_len + 1, hop_len):
                end = start + window_len
                chunk = processed[start:end]
                emb = self._encoder.embed_utterance(chunk)
                sim = float(np.dot(emb, target_emb) / (
                    np.linalg.norm(emb) * np.linalg.norm(target_emb) + 1e-8
                ))
                # Soft mask: scale linearly from 0 at threshold-0.1 to 1 at threshold
                weight = np.clip((sim - self.similarity_threshold + 0.1) / 0.1, 0.0, 1.0)
                mask[start:end] += weight
                counts[start:end] += 1.0

            counts = np.maximum(counts, 1.0)
            mask = mask / counts

            # Apply mask to original audio (not preprocessed)
            if len(audio_16k) == len(mask):
                return audio_16k * mask
            # Length mismatch — resample mask
            from numpy import interp
            x_mask = np.linspace(0, 1, len(mask))
            x_audio = np.linspace(0, 1, len(audio_16k))
            resampled_mask = interp(x_audio, x_mask, mask)
            return audio_16k * resampled_mask

        except Exception:
            return audio_16k

    def extract_loudest(self, audio_16k: np.ndarray) -> np.ndarray:
        """Simple loudness-based extraction — keep segments above median energy."""
        frame_len = int(0.025 * 16000)  # 25ms frames
        hop = int(0.010 * 16000)        # 10ms hop

        n_frames = max(1, (len(audio_16k) - frame_len) // hop + 1)
        energies = np.zeros(n_frames)
        for i in range(n_frames):
            start = i * hop
            frame = audio_16k[start:start + frame_len]
            energies[i] = np.sqrt(np.mean(frame ** 2))

        threshold = np.median(energies) * 1.5
        mask = np.zeros(len(audio_16k), dtype=np.float32)

        for i in range(n_frames):
            if energies[i] >= threshold:
                start = i * hop
                end = min(start + frame_len, len(audio_16k))
                mask[start:end] = 1.0

        # Smooth the mask to avoid clicks
        kernel_size = int(0.05 * 16000)
        if kernel_size > 0:
            kernel = np.ones(kernel_size) / kernel_size
            mask = np.convolve(mask, kernel, mode='same')
            mask = np.clip(mask, 0.0, 1.0)

        return audio_16k * mask

    def enroll_voice(self, name: str, audio_clips: List[np.ndarray]) -> bool:
        """Enroll a speaker from multiple audio clips. Saves embedding to disk."""
        if self._encoder is None:
            return False

        try:
            from resemblyzer import preprocess_wav
            embeddings = []
            for clip in audio_clips:
                processed = preprocess_wav(clip, source_sr=16000)
                if len(processed) >= 1600:
                    emb = self._encoder.embed_utterance(processed)
                    embeddings.append(emb)

            if not embeddings:
                return False

            avg_embedding = np.mean(embeddings, axis=0)
            np.save(self.enrollment_dir / f"{name}.npy", avg_embedding)
            self._known_embeddings[name] = avg_embedding
            print(f"[SPEAKER] Enrolled voice: {name} ({len(embeddings)} clips)")
            return True
        except Exception:
            return False

    def isolate(self, audio_16k: np.ndarray, person_id: Optional[str] = None) -> np.ndarray:
        """Full isolation pipeline: denoise → extract target speaker.

        DeepFilterNet removes non-speech noise (fans, HVAC) but can't separate
        speech-from-speech — that requires enrolled voice extraction via Resemblyzer.
        Only denoise when we have an enrollment target to extract afterward.
        """
        has_target = (
            (person_id and person_id in self._known_embeddings)
            or self._known_embeddings
        )

        audio = self.denoise(audio_16k) if has_target else audio_16k

        if person_id and person_id in self._known_embeddings:
            return self.extract_speaker(audio, person_id).astype(np.float32)

        if self._known_embeddings:
            name, sim = self.identify_speaker(audio)
            if name != "unknown":
                return self.extract_speaker(audio, name).astype(np.float32)

        return audio_16k.astype(np.float32)

    @property
    def enrolled_speakers(self) -> list[str]:
        return list(self._known_embeddings.keys())
