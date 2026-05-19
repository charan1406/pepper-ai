#!/usr/bin/env python3
"""Test: Vision + LLM running simultaneously on 4GB VRAM.

Verifies: webcam capture → YOLO26n → InsightFace → scene text → 4B brain chat.
All perception on CPU, brain on GPU — should coexist on RTX 3050 4GB.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pepper.client import PepperClient
import config

BRIDGE = "http://localhost:5001"
BRAIN = config.BRAIN_URL


def timed(label, fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    dt = (time.perf_counter() - t0) * 1000
    print(f"  {label}: {dt:.0f}ms")
    return result


def check_services():
    from brains.llm_client import LLMClient
    pepper = PepperClient(BRIDGE)
    if not pepper.is_alive():
        print(f"✗ Bridge not reachable at {BRIDGE}")
        print("  Run: ./simulator/start_bridge.sh")
        return False

    client = LLMClient(base_url=BRAIN)
    if not client.is_alive():
        print(f"✗ Brain not reachable at {BRAIN}")
        print("  Run: ./start_dev.sh")
        return False

    print(f"✓ Bridge alive at {BRIDGE}")
    print(f"✓ Brain alive at {BRAIN}")
    return True


def test_vision_standalone():
    """Step 1: Test vision pipeline alone (baseline timings)."""
    print("\n── Step 1: Vision Pipeline (standalone) ──")
    from perception.vision import VisionPipeline

    pepper = PepperClient(BRIDGE)

    vision = timed("Load YOLO26n + InsightFace", VisionPipeline)

    frame = timed("Capture webcam frame", pepper.get_camera_frame)
    if not frame:
        print("  ✗ No frame from bridge")
        return None, None
    print(f"  Frame: {len(frame)} chars base64")

    scene = timed("YOLO + InsightFace", vision.process_frame, frame)
    print(f"  Objects: {[f'{o.label} ({o.confidence:.0%})' for o in scene.objects]}")
    print(f"  Faces: {[f'{f.name} ({f.confidence:.0%})' for f in scene.faces]}")
    print(f"  People: {scene.people_count}")

    return vision, pepper


def test_llm_standalone():
    """Step 2: Test LLM alone (baseline timing)."""
    print("\n── Step 2: LLM Chat (standalone) ──")
    from brains.llm_client import LLMClient

    client = LLMClient(base_url=BRAIN)

    t0 = time.perf_counter()
    response = client.chat(
        "Hello, who are you?",
        system="You are Pepper, a friendly robot. Reply in one sentence.",
        profile="social",
    )
    dt = (time.perf_counter() - t0) * 1000
    print(f"  Response ({dt:.0f}ms): {response.spoken_text[:120]}")
    print(f"  Tokens: {response.completion_tokens} out, {response.tok_per_sec:.1f} tok/s")
    return True


def test_combined():
    """Step 3: Vision + LLM together — the real test."""
    print("\n── Step 3: Vision + LLM Combined ──")
    from perception.vision import VisionPipeline
    from perception.scene import SceneManager
    from brains.llm_client import LLMClient

    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()
    scene_mgr = SceneManager(pepper, vision)
    client = LLMClient(base_url=BRAIN)

    scene_mgr.start()
    print("  Scene manager running (background thread)...")
    time.sleep(2)

    scene_text = scene_mgr.scene_text()
    print(f"  Scene: {scene_text}")

    system = f"You are Pepper, a friendly robot assistant.\nCurrent scene: {scene_text}\nDescribe what you see, then greet anyone present. One sentence each."

    t0 = time.perf_counter()
    response = client.chat("What do you see right now?", system=system, profile="social")
    dt = (time.perf_counter() - t0) * 1000
    print(f"  LLM response ({dt:.0f}ms): {response.spoken_text[:200]}")

    time.sleep(0.5)
    scene_after = scene_mgr.scene_text()
    print(f"  Scene after LLM: {scene_after}")

    scene_mgr.stop()
    return True


def test_continuous_load():
    """Step 4: Sustained load — 5 vision+LLM cycles."""
    print("\n── Step 4: Sustained Load (5 cycles) ──")
    from perception.vision import VisionPipeline
    from brains.llm_client import LLMClient

    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()
    client = LLMClient(base_url=BRAIN)

    prompts = [
        "What objects do you see?",
        "Is anyone here?",
        "Describe the room.",
        "What's in front of you?",
        "How many people are nearby?",
    ]

    timings = []
    for i, prompt in enumerate(prompts):
        t0 = time.perf_counter()

        frame = pepper.get_camera_frame()
        if not frame:
            print(f"  [{i+1}] ✗ No frame")
            continue
        scene = vision.process_frame(frame)
        obj_labels = list(set(o.label for o in scene.objects))
        face_names = [f.name for f in scene.faces]
        scene_text = f"Objects: {obj_labels}, Faces: {face_names}, People: {scene.people_count}"

        response = client.chat(
            prompt,
            system=f"You are Pepper. Scene: {scene_text}. Reply in one short sentence.",
            profile="social",
        )
        dt = (time.perf_counter() - t0) * 1000
        timings.append(dt)
        print(f"  [{i+1}] {dt:.0f}ms | {scene_text[:60]}... → {response.spoken_text[:80]}")

    avg = sum(timings) / len(timings)
    print(f"\n  Average cycle: {avg:.0f}ms ({avg/1000:.1f}s)")
    print(f"  Range: {min(timings):.0f}ms – {max(timings):.0f}ms")
    return True


if __name__ == "__main__":
    print("=" * 55)
    print("  PEPPER AI — Vision + LLM Integration Test")
    print("  RTX 3050 4GB: YOLO+InsightFace(CPU) + 4B(GPU)")
    print("=" * 55)

    if not check_services():
        sys.exit(1)

    test_vision_standalone()
    test_llm_standalone()
    test_combined()
    test_continuous_load()

    print("\n" + "=" * 55)
    print("  All tests complete")
    print("=" * 55)
