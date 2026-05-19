#!/usr/bin/env python3
"""Test: Live voice loop — speak into mic → STT → Brain → TTS response.

This is the actual Pepper interaction flow without typing.
Requires: sim bridge (5001), 4B brain (8090) running.
Speak into your laptop mic when prompted. Ctrl+C to stop.
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pepper.client import PepperClient
from brains.llm_client import LLMClient, Message
from perception.stt import SpeechToText
from tts.router import TTSRouter
import config

BRIDGE = "http://localhost:5001"


def main():
    print("=" * 55)
    print("  PEPPER AI — Live Voice Loop Test")
    print("  Speak into your mic. Ctrl+C to stop.")
    print("=" * 55)

    pepper = PepperClient(BRIDGE)
    if not pepper.is_alive():
        print(f"\n✗ Bridge not reachable at {BRIDGE}")
        sys.exit(1)

    brain = LLMClient(base_url=config.BRAIN_URL)
    if not brain.is_alive():
        print(f"\n✗ Brain not reachable at {config.BRAIN_URL}")
        sys.exit(1)

    print("\nLoading STT (Whisper + VAD)...")
    stt = SpeechToText()

    print("Loading TTS (Kokoro)...")
    tts = TTSRouter(pepper)

    history = []
    system = "You are Pepper, a friendly robot assistant. Keep responses to 1-2 sentences. Be natural and conversational."

    print("\n✓ All systems ready. Listening...\n")

    turn = 0
    while True:
        try:
            print(f"--- Turn {turn + 1}: Recording 4s... speak now! ---")
            t0 = time.perf_counter()
            wav = pepper.record_audio(seconds=4)
            rec_ms = (time.perf_counter() - t0) * 1000

            if not wav:
                print(f"  No audio from bridge ({rec_ms:.0f}ms)")
                continue

            t0 = time.perf_counter()
            result = stt.transcribe_wav_bytes(wav)
            stt_ms = (time.perf_counter() - t0) * 1000

            if not result or not result.text.strip():
                print(f"  (silence — VAD filtered, {stt_ms:.0f}ms)")
                continue

            print(f"  Heard ({stt_ms:.0f}ms, {result.language}): \"{result.text}\"")

            # Send to brain
            t0 = time.perf_counter()
            resp = brain.chat(
                result.text,
                system=system,
                history=history[-10:],
                profile="social",
            )
            llm_ms = (time.perf_counter() - t0) * 1000

            if not resp.success:
                print(f"  Brain error ({llm_ms:.0f}ms): {resp.error}")
                continue

            spoken = resp.spoken_text
            print(f"  Brain ({llm_ms:.0f}ms, {resp.tok_per_sec:.0f}tok/s): \"{spoken}\"")

            # Speak response via TTS
            t0 = time.perf_counter()
            tts.speak(spoken, result.language if result.language in ("en", "de") else "en")
            tts_ms = (time.perf_counter() - t0) * 1000
            print(f"  TTS: {tts_ms:.0f}ms")

            # Update history
            history.append(Message("user", result.text))
            history.append(Message("assistant", spoken))

            total = rec_ms + stt_ms + llm_ms + tts_ms
            print(f"  Total: {total:.0f}ms (rec={rec_ms:.0f} stt={stt_ms:.0f} llm={llm_ms:.0f} tts={tts_ms:.0f})")

            turn += 1

        except KeyboardInterrupt:
            print("\n\nStopping...")
            break

    print(f"\nCompleted {turn} voice turns.")


if __name__ == "__main__":
    main()
