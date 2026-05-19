#!/usr/bin/env python3
"""Full System Test — every component, end-to-end.

Expects: sim bridge (5001), 4B brain (8090), SearXNG (8080) running.
Run: python test_full_system.py
"""

import sys
import os
import time
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pepper.client import PepperClient
import config

BRIDGE = "http://localhost:5001"
BRAIN_URL = config.BRAIN_URL
passed = 0
failed = 0
skipped = 0


def test(name, fn):
    global passed, failed, skipped
    try:
        result = fn()
        if result == "SKIP":
            print(f"  ⊘ {name} — skipped")
            skipped += 1
        elif result:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name} — returned False")
            failed += 1
    except Exception as e:
        print(f"  ✗ {name} — {type(e).__name__}: {e}")
        failed += 1


# ━━━ 1. Bridge & Client ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_bridge():
    print("\n── 1. Bridge & Client ──")
    pepper = PepperClient(BRIDGE)

    test("Bridge alive", lambda: pepper.is_alive())
    test("Health endpoint", lambda: pepper.health() is not None)
    test("Battery status", lambda: pepper.battery() is not None)
    test("Get camera frame", lambda: pepper.get_camera_frame() is not None)
    test("Set posture", lambda: pepper.set_posture("Stand") or True)
    test("Get posture", lambda: isinstance(pepper.get_posture(), str))
    test("Speak", lambda: pepper.speak("Testing.") or True)
    test("Set head", lambda: pepper.set_head(yaw=0.0, pitch=0.0) or True)
    test("Eye color", lambda: pepper.eyes_white() or True)


# ━━━ 2. Reflex Brain ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_reflex():
    print("\n── 2. Reflex Brain ──")
    from brains.reflex import ReflexBrain

    reflex = ReflexBrain()

    test("Match 'go forward'", lambda: reflex.match("go forward").command == "forward")
    test("Match 'stopp' (German)", lambda: reflex.match("stopp").command == "stop")
    test("Match 'sit down'", lambda: reflex.match("sit down").command == "sit")
    test("No match 'hello'", lambda: reflex.match("hello there") is None)
    test("Match 'turn left'", lambda: reflex.match("please turn left").command == "left")
    test("Execute on bridge", lambda: (
        reflex.execute(reflex.match("go forward"), PepperClient(BRIDGE)) or True
    ))


# ━━━ 3. Router ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_router():
    print("\n── 3. Router ──")
    from core.router import Router, Route

    router = Router()

    test("Reflex route for 'stop'", lambda: router.route("stop").route == Route.REFLEX)
    test("Deep route for 'hello'", lambda: router.route("hello there").route == Route.DEEP)
    test("Deep route for question", lambda: router.route("What is the weather?").route == Route.DEEP)
    test("Reflex route 'dance'", lambda: router.route("dance").route == Route.REFLEX)


# ━━━ 4. LLM Client ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_llm():
    print("\n── 4. LLM Client ──")
    from brains.llm_client import LLMClient, Message

    client = LLMClient(base_url=BRAIN_URL)

    test("Health check", lambda: client.is_alive())

    def test_chat():
        resp = client.chat("Say 'pong'.", system="Reply with exactly one word.", profile="social")
        assert resp.success, f"Failed: {resp.error}"
        assert resp.content.strip(), "Empty content"
        assert resp.completion_tokens > 0, "Zero completion tokens"
        return True
    test("Chat (basic)", test_chat)

    def test_thinking():
        resp = client.chat("What is 15 * 23?", system="Show your work, then answer.", profile="social")
        assert resp.success, f"Failed: {resp.error}"
        assert resp.thinking, "No thinking content"
        assert resp.content.strip(), "Empty content"
        return True
    test("Chat (thinking mode)", test_thinking)

    def test_history():
        history = [
            Message("user", "My name is TestBot."),
            Message("assistant", "Nice to meet you, TestBot!"),
        ]
        resp = client.chat("What is my name?", system="You are a helpful robot.", history=history, profile="social")
        assert resp.success, f"Failed: {resp.error}"
        return True
    test("Chat (with history)", test_history)

    def test_streaming():
        gen = client._call_stream(
            [{"role": "system", "content": "Reply in one word."},
             {"role": "user", "content": "Say hello."}],
            max_tokens=200,
            **{"temperature": 0.7, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5},
        )
        tokens = []
        try:
            while True:
                token = next(gen)
                tokens.append(token)
        except StopIteration as e:
            resp = e.value
        assert resp.success, f"Stream failed: {resp.error}"
        assert len(tokens) > 0, "No tokens streamed"
        return True
    test("Streaming", test_streaming)

    def test_json():
        result = client.generate_json(
            "What is 2+2? Respond as JSON with key 'answer'.",
            system="Always respond with valid JSON.",
        )
        assert result is not None, "No JSON parsed"
        assert "answer" in result, f"Missing 'answer' key: {result}"
        return True
    test("JSON generation", test_json)


# ━━━ 5. Vision ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_vision():
    print("\n── 5. Vision Pipeline ──")
    from perception.vision import VisionPipeline

    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()

    def test_yolo():
        frame = pepper.get_camera_frame()
        assert frame, "No frame"
        objects = vision.detect_objects(vision._decode_frame(frame))
        print(f"    → {[o.label for o in objects]}")
        return True
    test("YOLO object detection", test_yolo)

    def test_faces():
        frame = pepper.get_camera_frame()
        assert frame, "No frame"
        faces = vision.detect_faces(vision._decode_frame(frame))
        print(f"    → {len(faces)} face(s) detected")
        return True
    test("InsightFace detection", test_faces)

    def test_process_frame():
        frame = pepper.get_camera_frame()
        assert frame, "No frame"
        scene = vision.process_frame(frame)
        assert scene.timestamp > 0, "No timestamp"
        return True
    test("Full frame processing", test_process_frame)


# ━━━ 6. Scene Manager ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_scene():
    print("\n── 6. Scene Manager ──")
    from perception.vision import VisionPipeline
    from perception.scene import SceneManager

    pepper = PepperClient(BRIDGE)
    vision = VisionPipeline()
    scene_mgr = SceneManager(pepper, vision)

    def test_scene():
        scene_mgr.start()
        time.sleep(2)
        text = scene_mgr.scene_text()
        scene_mgr.stop()
        print(f"    → {text}")
        assert text, "Empty scene text"
        return True
    test("Background scene loop", test_scene)


# ━━━ 7. STT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_stt():
    print("\n── 7. Speech-to-Text ──")
    from perception.stt import SpeechToText

    def test_stt_init():
        stt = SpeechToText()
        assert stt.model is not None, "Model not loaded"
        return True
    test("Whisper model load", test_stt_init)

    def test_stt_audio():
        pepper = PepperClient(BRIDGE)
        stt = SpeechToText()
        wav = pepper.record_audio(seconds=2)
        if not wav:
            print("    → No audio from bridge (mic may be unavailable)")
            return "SKIP"
        result = stt.transcribe_wav_bytes(wav)
        if result:
            print(f"    → Heard: \"{result.text}\" ({result.language})")
        else:
            print("    → Silence/noise (VAD working)")
        return True
    test("Record + transcribe (2s)", test_stt_audio)


# ━━━ 8. Memory Vault ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_vault():
    print("\n── 8. Memory Vault ──")
    from memory.vault import Vault

    vault = Vault()

    test("Read system prompt", lambda: vault.read("system/deep_brain.md") is not None)
    test("Read personality", lambda: vault.read("system/personality.md") is not None)
    test("Read rules", lambda: vault.read("system/rules.md") is not None)
    test("File exists", lambda: vault.exists("system/deep_brain.md"))
    test("File not exists", lambda: not vault.exists("system/nonexistent.md"))
    test("List people dir", lambda: isinstance(vault.list_files("people"), list))

    def test_fts_search():
        results = vault.search("Pepper robot")
        assert isinstance(results, list), "Search returned non-list"
        print(f"    → {len(results)} results")
        if results:
            print(f"    → Top: {results[0]['path']}")
        return True
    test("FTS5 search", test_fts_search)

    def test_backlinks():
        results = vault.find_backlinks("people/_template")
        print(f"    → {len(results)} backlinks found")
        return isinstance(results, list)
    test("Find backlinks", test_backlinks)

    def test_write_read():
        vault.write("_test_temp.md", "# Test\nHello from test suite.")
        content = vault.read("_test_temp.md")
        assert content and "Hello from test suite" in content
        results = vault.search("test suite")
        found = any("_test_temp" in r["path"] for r in results)
        os.unlink(os.path.join(vault.root, "_test_temp.md"))
        assert found, "Written file not found in FTS index"
        return True
    test("Write + search round-trip", test_write_read)


# ━━━ 9. Person Memory ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_person():
    print("\n── 9. Person Memory ──")
    from memory.person import PersonMemory

    pm = PersonMemory()

    test("id_from_name", lambda: pm.id_from_name("John Smith") == "john_smith")

    def test_create_flow():
        pid = "_test_person"
        content = pm.create(pid, "Test Person", language="en")
        assert pm.exists(pid), "Not created"
        ctx = pm.get_quick_context(pid)
        assert ctx and "Test Person" in ctx, f"Bad context: {ctx}"
        pm.add_context(pid, "Likes robots")
        pm.update_last_seen(pid)
        pm.log_conversation(pid, "hello", "hi there")
        updated = pm.get(pid)
        assert "Likes robots" in updated, "Context not added"
        assert "hello" in updated, "Conversation not logged"
        # Cleanup
        os.unlink(os.path.join(pm.vault.root, f"people/{pid}.md"))
        return True
    test("Create → context → log → cleanup", test_create_flow)

    test("List people", lambda: isinstance(pm.list_people(), list))


# ━━━ 10. Web Search ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_search():
    print("\n── 10. Web Search (SearXNG) ──")
    from tools.web_search import WebSearch

    ws = WebSearch()

    def test_search():
        results = ws.search("Python programming language", max_results=3)
        assert len(results) > 0, "No results"
        print(f"    → {len(results)} results, top: {results[0].title[:60]}")
        return True
    test("Search query", test_search)

    def test_format():
        results = ws.search("Pepper robot Softbank")
        formatted = ws.format_for_llm(results)
        assert len(formatted) > 0, "Empty format"
        print(f"    → {len(formatted)} chars formatted")
        return True
    test("Format for LLM", test_format)

    def test_cache():
        ws2 = WebSearch()
        ws2.search("cache test query")
        assert "cache test query" in ws2.cache
        t0 = time.perf_counter()
        ws2.search("cache test query")
        dt = (time.perf_counter() - t0) * 1000
        print(f"    → Cached hit in {dt:.1f}ms")
        return dt < 10
    test("Cache hit", test_cache)

    test("Tool definition", lambda: ws.tool_definition()["function"]["name"] == "web_search")


# ━━━ 11. TTS Router ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_tts():
    print("\n── 11. TTS Router ──")
    from tts.router import TTSRouter

    pepper = PepperClient(BRIDGE)
    tts = TTSRouter(pepper)

    def test_kokoro():
        wav = tts.kokoro_to_wav("Hello from Pepper.", "en")
        if wav:
            print(f"    → {len(wav)} bytes WAV")
            return True
        print("    → Kokoro not available")
        return "SKIP"
    test("Kokoro TTS render", test_kokoro)

    def test_speak():
        result = tts.speak("Testing.", "en")
        return True
    test("Speak via router", test_speak)


# ━━━ 12. Filler Audio ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_filler():
    print("\n── 12. Filler Audio ──")
    from tts.filler import FillerPlayer

    pepper = PepperClient(BRIDGE)

    def test_filler():
        t0 = time.perf_counter()
        filler = FillerPlayer(pepper, languages=["en"])
        dt = (time.perf_counter() - t0) * 1000
        cached = len(filler._cache.get("en", []))
        print(f"    → {cached} clips cached in {dt:.0f}ms")
        assert cached > 0, "No filler clips cached"
        return True
    test("Pre-cache English fillers", test_filler)

    def test_play():
        filler = FillerPlayer(pepper, languages=["en"])
        filler.play("en")
        return True
    test("Play filler", test_play)


# ━━━ 13. Tool Calling ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_tool_calling():
    print("\n── 13. Tool Calling (LLM → search → respond) ──")
    from brains.llm_client import LLMClient
    from tools.web_search import WebSearch

    client = LLMClient(base_url=BRAIN_URL)
    ws = WebSearch()

    def test_tool_call():
        messages = [
            {"role": "system", "content": "You have tools available. Use web_search when you need current information."},
            {"role": "user", "content": "Search the web for the current president of Germany."},
        ]
        resp = client._call(
            messages, max_tokens=2000,
            tools=[ws.tool_definition()],
            temperature=0.1, top_p=0.9, top_k=20, min_p=0.0, presence_penalty=0.0,
        )
        assert resp.success, f"Failed: {resp.error}"
        if resp.has_tool_calls:
            tc = resp.tool_calls[0]
            print(f"    → Tool call: {tc['name']}({tc['arguments']})")
            query = tc["arguments"].get("query", "") if isinstance(tc["arguments"], dict) else json.loads(tc["arguments"]).get("query", "")
            results = ws.search(query)
            formatted = ws.format_for_llm(results)
            print(f"    → Got {len(results)} results")

            messages.append({"role": "assistant", "content": resp.content or None,
                             "tool_calls": [{"id": "call_0", "type": "function",
                                             "function": {"name": tc["name"],
                                                          "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else tc["arguments"]}}]})
            messages.append({"role": "tool", "tool_call_id": "call_0", "content": formatted})

            resp2 = client._call(messages, max_tokens=2000,
                                 temperature=0.7, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5)
            assert resp2.success, f"Second call failed: {resp2.error}"
            print(f"    → Final: {resp2.content[:120]}")
            return True
        else:
            print(f"    → No tool call (model answered directly): {resp.content[:80]}")
            return True
    test("Full tool loop", test_tool_call)


# ━━━ 14. Circuit Breaker ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_supervisor():
    print("\n── 14. Circuit Breaker & Supervisor ──")
    from core.supervisor import CircuitBreaker, Supervisor
    from brains.llm_client import LLMClient

    breaker = CircuitBreaker(failure_threshold=3, reset_timeout=1.0)

    test("Initially closed", lambda: breaker.can_call("test"))

    def test_open():
        for _ in range(3):
            breaker.record_failure("test")
        assert not breaker.can_call("test"), "Should be open"
        return True
    test("Opens after 3 failures", test_open)

    def test_half_open():
        time.sleep(1.1)
        assert breaker.can_call("test"), "Should be half-open"
        breaker.record_success("test")
        assert breaker.can_call("test"), "Should be closed after success"
        return True
    test("Half-open → recover", test_half_open)

    def test_supervisor():
        client = LLMClient(base_url=BRAIN_URL)
        sup = Supervisor(client)
        health = sup.health_check()
        assert health["brain_alive"], "Brain not alive"
        assert health["degradation_level"] == 0, f"Degraded: {health}"
        return True
    test("Supervisor health check", test_supervisor)


# ━━━ 15. Health Monitor ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_health():
    print("\n── 15. Health Monitor ──")
    from core.health import HealthMonitor

    hm = HealthMonitor(log_dir="/tmp/pepper_test_logs")

    def test_log():
        hm.log_event("test", {"msg": "integration test"})
        hm.log_llm_call("brain", tokens=100, latency=1.5, tok_per_sec=30.0, success=True)
        hm.log_interaction("hello", "hi there", route="deep")
        hm.log_error("test", "simulated error")
        hm.close()
        # Verify log file has entries
        log_files = list(hm.log_dir.glob("*.jsonl"))
        assert log_files, "No log files"
        lines = log_files[0].read_text().strip().split("\n")
        assert len(lines) >= 4, f"Only {len(lines)} log lines"
        parsed = json.loads(lines[-1])
        assert "ts" in parsed, "Missing timestamp"
        return True
    test("Write + read structured logs", test_log)

    def test_heartbeat():
        hm2 = HealthMonitor(log_dir="/tmp/pepper_test_logs")
        hm2.write_heartbeat("/tmp/pepper_test_heartbeat")
        hm2.close()
        import os
        assert os.path.exists("/tmp/pepper_test_heartbeat")
        os.unlink("/tmp/pepper_test_heartbeat")
        return True
    test("Heartbeat file", test_heartbeat)

    def test_p95():
        hm3 = HealthMonitor(log_dir="/tmp/pepper_test_logs")
        for lat in [1.0, 1.5, 2.0, 2.5, 3.0, 10.0]:
            hm3.log_llm_call("brain", 100, lat, 30.0, True)
        p95 = hm3.get_p95_latency("llm_latency")
        hm3.close()
        assert p95 > 0, "P95 is zero"
        print(f"    → P95 latency: {p95:.1f}s")
        return True
    test("P95 metric calculation", test_p95)


# ━━━ 16. Watchdog ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def section_watchdog():
    print("\n── 16. Watchdog ──")
    import core.watchdog as wd
    from pathlib import Path

    def test_watchdog_stale():
        hb = "/tmp/pepper_test_wd_heartbeat"
        Path(hb).write_text(str(time.time() - 999))
        orig = wd.HEARTBEAT_PATH
        wd.HEARTBEAT_PATH = hb
        assert wd.is_stale(), "Should be stale"
        wd.HEARTBEAT_PATH = orig
        Path(hb).unlink()
        return True
    test("Detect stale heartbeat", test_watchdog_stale)

    def test_watchdog_fresh():
        hb = "/tmp/pepper_test_wd_heartbeat2"
        Path(hb).write_text(str(time.time()))
        orig = wd.HEARTBEAT_PATH
        wd.HEARTBEAT_PATH = hb
        assert not wd.is_stale(), "Should be fresh"
        wd.HEARTBEAT_PATH = orig
        Path(hb).unlink()
        return True
    test("Detect fresh heartbeat", test_watchdog_fresh)


# ━━━ Run All ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    print("=" * 60)
    print("  PEPPER AI — Full System Integration Test")
    print("=" * 60)

    # Pre-flight
    pepper = PepperClient(BRIDGE)
    if not pepper.is_alive():
        print(f"\n✗ Bridge not reachable at {BRIDGE}")
        sys.exit(1)

    t_start = time.perf_counter()

    section_bridge()
    section_reflex()
    section_router()
    section_llm()
    section_vision()
    section_scene()
    section_stt()
    section_vault()
    section_person()
    section_search()
    section_tts()
    section_filler()
    section_tool_calling()
    section_supervisor()
    section_health()
    section_watchdog()

    total_time = time.perf_counter() - t_start

    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"  Total time: {total_time:.1f}s")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)
