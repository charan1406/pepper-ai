#!/usr/bin/env python3
"""Phase 2 Test — Perception Pipeline"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pepper.client import PepperClient

BRIDGE = "http://localhost:5001"


def test_vision():
    print("── TEST: Vision Pipeline ──")
    from perception.vision import VisionPipeline

    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()

    frame = pepper.get_camera_frame()
    if not frame:
        print("  ✗ No frame from bridge")
        return False

    print(f"  Frame received: {len(frame)} bytes (base64)")
    scene = vision.process_frame(frame)
    print(f"  ✓ Objects: {[f'{o.label} ({o.confidence:.0%})' for o in scene.objects]}")
    print(f"  ✓ Faces: {[f'{f.name} ({f.confidence:.0%})' for f in scene.faces]}")
    print(f"  ✓ People count: {scene.people_count}")
    return True


def test_scene_manager():
    print("\n── TEST: Scene Manager ──")
    from perception.vision import VisionPipeline
    from perception.scene import SceneManager

    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()
    scene_mgr = SceneManager(pepper, vision)

    scene_mgr.start()
    print("  Running scene manager for 5 seconds...")
    for i in range(5):
        time.sleep(1)
        text = scene_mgr.scene_text()
        print(f"  [{i + 1}s] {text}")
    scene_mgr.stop()
    print("  ✓ Scene manager test complete")
    return True


def test_stt():
    print("\n── TEST: Speech-to-Text ──")
    from perception.stt import SpeechToText

    pepper = PepperClient(BRIDGE)
    stt = SpeechToText()

    print("  Recording 3 seconds... speak now!")
    wav = pepper.record_audio(seconds=3)
    if not wav:
        print("  ✗ No audio from bridge")
        return False

    print(f"  Audio received: {len(wav)} bytes (base64)")
    result = stt.transcribe_wav_bytes(wav)
    if result:
        print(f"  ✓ Heard: \"{result.text}\"")
        print(f"    Language: {result.language} ({result.confidence:.0%})")
        print(f"    Duration: {result.duration:.1f}s")
    else:
        print("  ⚠ No speech detected (silence or noise — VAD working correctly)")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("  PEPPER AI — Phase 2 Perception Tests")
    print("=" * 50)

    # Check bridge
    pepper = PepperClient(BRIDGE)
    if not pepper.is_alive():
        print(f"\n✗ Bridge not reachable at {BRIDGE}")
        print("  Run: ./simulator/start_bridge.sh")
        sys.exit(1)
    print(f"\n✓ Bridge alive at {BRIDGE}\n")

    test_vision()
    test_scene_manager()
    test_stt()

    print("\n" + "=" * 50)
    print("  Phase 2 tests complete")
    print("=" * 50)
