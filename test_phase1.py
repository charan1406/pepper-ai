#!/usr/bin/env python3
"""
Phase 1 Test — Bridge Client + LLM Client
============================================
Usage: python test_phase1.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pepper.client import PepperClient
from brains.llm_client import LLMClient, Message

BRIDGE_URL = "http://localhost:5001"
DEEP_URL = "http://localhost:8090/v1"
FAST_URL = "http://localhost:8091/v1"

PEPPER_SYSTEM = """You are Pepper, a friendly humanoid robot in a university robotics lab in Germany. 
You are warm, curious, and brief. Keep spoken responses to 2-3 sentences.
Respond in the same language the user speaks."""


def header(text):
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")

def ok(label):
    print(f"  ✓ {label}")

def fail(label):
    print(f"  ✗ {label}")

def info(label, value=""):
    print(f"    {label}: {value}" if value else f"    {label}")

def show_resp(resp, label="Response"):
    """Show a brain response with all diagnostics."""
    if resp.success and not resp.is_empty:
        ok(f"{label}: \"{resp.spoken_text}\"")
        info("Speed", f"{resp.tok_per_sec:.0f} tok/s | {resp.wall_time:.1f}s")
        if resp.thinking:
            info("Thinking", f"{len(resp.thinking)} chars")
    elif resp.escalated:
        ok("ESCALATED (correctly refused)")
    elif resp.success and resp.is_empty:
        fail(f"Empty content — thinking: {len(resp.thinking)}c, "
             f"tokens: {resp.completion_tokens}")
    else:
        fail(f"Error: {resp.error}")


# ─── Tests ───────────────────────────────────────────────────────

def test_bridge():
    header("TEST 1 — Bridge Connection")
    pepper = PepperClient(BRIDGE_URL)

    if not pepper.is_alive():
        fail("Bridge not reachable — run start_bridge.sh")
        return False

    ok(f"Bridge alive")
    ok(f"Battery: {pepper.battery()['level']}%")
    pos = pepper.get_position()
    ok(f"Position: x={pos[0]:.2f} y={pos[1]:.2f} θ={pos[2]:.2f}")
    ok(f"Posture: {pepper.get_posture()}")
    return True


def test_actions():
    header("TEST 2 — Pepper Actions (watch 3D view!)")
    p = PepperClient(BRIDGE_URL)

    print("  Speaking + eyes green...")
    p.eyes_speaking()
    p.speak("Hello! I am Pepper!", language="en")
    time.sleep(2)

    print("  Head scan...")
    p.eyes_blue()
    p.look_left(1.0); time.sleep(1)
    p.look_right(1.0); time.sleep(1)
    p.look_center(); time.sleep(0.5)

    print("  Moving forward 1.5m...")
    p.eyes_white()
    p.move_to(1.5, 0, 0); time.sleep(3)

    print("  Waving...")
    p.wave(); time.sleep(2)

    print("  Navigate to coffee machine...")
    p.navigate_to(0.5, 5.0, 1.57); time.sleep(4)

    print("  German speech...")
    p.speak("Hallo! Möchten Sie einen Kaffee?", language="de")
    time.sleep(2)

    print("  Returning home...")
    p.navigate_to(0.5, 0.5, 0); time.sleep(3)

    ok("All actions completed")


def test_llm():
    header("TEST 3 — LLM Brain Connection")
    deep = LLMClient(DEEP_URL, name="deep")
    fast = LLMClient(FAST_URL, name="fast")

    da = deep.is_alive()
    fa = fast.is_alive()

    ok("Deep brain (4B) alive") if da else info("Deep brain not running")
    ok("Fast brain (0.8B) alive") if fa else info("Fast brain not running")

    if not da and not fa:
        fail("No brains running!")
        return None
    return da, fa


def test_fast_filler(fast):
    header("TEST 4 — Fast Brain Filler Generation")
    tests = [
        ("What's the weather in Berlin?", "en", "John"),
        ("Wie spät ist es?", "de", None),
        ("Tell me about the Mars mission", "en", "Priya"),
    ]
    for query, lang, name in tests:
        print(f"\n  User: \"{query}\"")
        resp = fast.generate_filler(query, person_name=name, language=lang)
        show_resp(resp, "Filler")


def test_fast_social(fast):
    header("TEST 5 — Fast Brain Social Responses")
    tests = [
        ("Hi Pepper!", "en", "John"),
        ("Thanks!", "en", None),
        ("Guten Morgen!", "de", None),
        ("What's quantum computing?", "en", None),
    ]
    for query, lang, name in tests:
        print(f"\n  User: \"{query}\"")
        resp = fast.respond_social(query, person_name=name, language=lang)
        show_resp(resp, "Response")


def test_deep_query(deep):
    header("TEST 6 — Deep Brain Full Query")

    person_memory = """Name: John Smith
Prefers informal greeting ("Hey John")
Interested in cricket
Works in marketing department
Daughter's birthday coming up next week"""

    scene = "People: 1 detected (John Smith). Objects: desk, laptop, coffee cup."

    print("  Sending grounded query with person memory + scene...")
    resp = deep.deep_query(
        user_message="Hey Pepper! How's it going?",
        system=PEPPER_SYSTEM,
        person_memory=person_memory,
        scene=scene,
        profile="social",
    )
    show_resp(resp)


def test_deep_json(deep):
    header("TEST 7 — Deep Brain Structured JSON Output")
    print("  Asking for memory update JSON...")
    result = deep.generate_json(
        prompt='User said: "My name is Priya and I work in AI. I like chess."',
        system="Extract facts as JSON: {name, department, interests: []}",
    )
    if result:
        ok(f"Parsed JSON: {result}")
    else:
        fail("Failed to get valid JSON")


def test_combined(pepper, brain, brain_name):
    header(f"TEST 8 — Combined: {brain_name} → Pepper Speaks")

    print("  Asking the brain...")
    pepper.eyes_thinking()

    resp = brain.chat(
        "Someone just walked into the lab. Greet them warmly.",
        system=PEPPER_SYSTEM,
        profile="social",
    )

    if resp.success and not resp.is_empty:
        ok(f"Brain says: \"{resp.spoken_text}\"")
        info("Speed", f"{resp.tok_per_sec:.0f} tok/s | {resp.wall_time:.1f}s")

        print("  Pepper speaking...")
        pepper.eyes_speaking()
        pepper.speak(resp.spoken_text, language="en")
        pepper.wave()
        time.sleep(3)
        pepper.eyes_white()
        ok("Pepper spoke the brain's response!")
    else:
        fail(f"Brain failed: {resp.error}")


def interactive_chat(pepper, deep, fast, da, fa):
    header("INTERACTIVE CHAT")
    print("  /deep — switch to 4B  |  /fast — switch to 0.8B  |  /quit — exit\n")

    brain = deep if da else fast
    bname = "deep" if da else "fast"
    history = []

    while True:
        try:
            user = input(f"  [{bname}] You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user:
            continue
        if user == "/quit":
            break
        if user == "/deep" and da:
            brain, bname = deep, "deep"; print("  → deep"); continue
        if user == "/fast" and fa:
            brain, bname = fast, "fast"; print("  → fast"); continue

        pepper.eyes_thinking()
        history.append(Message("user", user))

        resp = brain.chat(user, system=PEPPER_SYSTEM, history=history[-8:], profile="social")

        if resp.success and not resp.is_empty:
            text = resp.spoken_text
            print(f"  [{bname}] Pepper: {text}")
            info(f"{resp.tok_per_sec:.0f} tok/s | {resp.wall_time:.1f}s | "
                 f"think: {len(resp.thinking)}c")
            history.append(Message("assistant", text))
            pepper.eyes_speaking()
            pepper.speak(text)
            time.sleep(max(1, len(text.split()) * 0.15))
            pepper.eyes_white()
        else:
            print(f"  [ERROR] {resp.error or 'empty response'}")

    pepper.eyes_white()
    print("\n  Goodbye!")


def main():
    print("=" * 60)
    print("  PEPPER AI — Phase 1 Test Suite")
    print("=" * 60)

    if not test_bridge():
        return

    test_actions()

    result = test_llm()
    if result is None:
        return
    da, fa = result

    deep = LLMClient(DEEP_URL, name="deep", thinking=True) if da else None
    fast = LLMClient(FAST_URL, name="fast", thinking=True) if fa else None
    pepper = PepperClient(BRIDGE_URL)

    if fast:
        test_fast_filler(fast)
        test_fast_social(fast)

    if deep:
        test_deep_query(deep)
        test_deep_json(deep)

    active = deep or fast
    aname = "deep" if deep else "fast"
    if active:
        test_combined(pepper, active, aname)

    header("TESTS COMPLETE")
    proceed = input("\n  Start interactive chat? (y/n): ").strip().lower()
    if proceed == "y":
        interactive_chat(pepper, deep, fast, da, fa)


if __name__ == "__main__":
    main()
