# Speaker Isolation Pipeline — Design Spec

## Problem
Pepper operates in a busy university lab. The laptop/robot mic picks up multiple conversations, background noise, and equipment hum. Whisper hallucinates on noisy audio. We need to isolate the target speaker before transcription.

## Approach: Target Speaker Extraction
DeepFilterNet (noise suppression) + Resemblyzer (voice embedding + spectral masking).

Total added latency budget: <500ms. Expected: ~130ms (80ms denoise + 50ms extraction).

## Audio Pipeline

```
Real Pepper (4 mics):
  mic array → beamforming (numpy, steered by head yaw angle)
    → DeepFilterNet ONNX (denoise, ~80ms)
    → Resemblyzer extraction (~50ms)
    → energy gate (RMS > 0.015)
    → Silero VAD
    → faster-whisper
    → text

Simulator (1 mic):
  laptop mic → DeepFilterNet → Resemblyzer → energy gate → VAD → Whisper → text
```

## New Module: `perception/speaker.py`

```python
class SpeakerIsolator:
    __init__(enrollment_dir, deepfilter_model, similarity_threshold)
    denoise(audio_16k: ndarray) -> ndarray           # DeepFilterNet, always runs
    extract_speaker(audio, speaker_id) -> ndarray     # Resemblyzer spectral mask
    extract_loudest(audio) -> ndarray                 # Loudness-based, no enrollment
    enroll_voice(name, audio_clips: list[ndarray])    # Save .npy voice embedding
    identify_speaker(audio) -> tuple[str, float]      # Match vs enrolled voices
    isolate(audio, person_id=None) -> ndarray         # Full pipeline: denoise + extract
```

### `isolate()` logic:
1. Always: `denoise(audio)`
2. If `person_id` provided and voice enrolled: `extract_speaker(audio, person_id)`
3. Elif enrolled voices exist: `identify_speaker(audio)` → extract if match > threshold
4. Else: `extract_loudest(audio)` (amplitude-based, no ML)

## Voice Enrollment
Mirrors face enrollment. Pepper captures 5-10s of the person talking, extracts a GE2E embedding via Resemblyzer, saves to `pepper_brain/voice_encodings/{name}.npy`. Orchestrator pairs face + voice enrollment in a single flow.

## Single vs Multi Speaker Mode
- **Single** (default): isolate one speaker, one transcription
- **Multi** (scene.people_count > 1 AND enrolled voices present): extract each enrolled speaker's audio, transcribe each separately, return `list[(speaker_id, text)]`
- Mode switch driven by SceneManager's people_count

## Integration Points

### STT (`perception/stt.py`)
`SpeechToText.__init__` accepts optional `SpeakerIsolator`. In `transcribe_wav_bytes`:
- After audio decode, before energy gate: `audio = self.isolator.isolate(audio, person_id)`
- Energy gate, VAD, Whisper proceed on cleaned audio

### Orchestrator / Main
- Pass `person_id` from face recognition into STT pipeline
- On enrollment: call both `vision.enroll_face()` and `isolator.enroll_voice()`

### Config (`config.py`)
```python
DEEPFILTER_MODEL = "DeepFilterNet3"
SPEAKER_SIMILARITY_THRESHOLD = 0.75
VOICE_ENCODINGS_DIR = "pepper_brain/voice_encodings"
SPEAKER_ISOLATION_ENABLED = True
```

## Dependencies
- `deepfilternet` (pip) — ONNX noise suppression, 7.7MB model
- `resemblyzer` (pip) — GE2E speaker encoder, 17MB model
- Both run on CPU. No GPU needed.

## What Doesn't Change
- Energy gate, Silero VAD, faster-whisper — unchanged
- VisionPipeline, SceneManager — unchanged
- All existing tests pass (isolator is optional, defaults to passthrough)

## Beamforming (Real Pepper only, future)
Pepper's 4-mic array enables delay-and-sum beamforming steered by HeadYaw angle. Implemented in the bridge as a preprocessing step before DeepFilterNet. Falls back to single-channel when on simulator. Not built now — added when we have the real robot.

## Success Criteria
1. Ambient noise no longer triggers Whisper hallucinations
2. Enrolled speakers are recognized and isolated in <200ms
3. Unknown speakers still work (denoise + loudest extraction)
4. Full system test passes with isolator enabled
5. Voice enrollment persists across restarts (.npy files)
