"""
Pepper Simulator — Bridge Server
==================================
HTTP server with IDENTICAL endpoints to the real Pepper bridge.
Swap config.BRIDGE_URL and the middleware works unchanged.

Runs on port 5001. Also runs a WebSocket server on port 5003
to broadcast state updates to the 3D web frontend.
"""

import json
import time
import base64
import struct
import threading
import asyncio
import hashlib
import wave
import io
import os
import sys

# Add parent dir to path so we can import brains/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from brains.llm_client import LLMClient, Message
    HAS_LLM = True
except ImportError:
    HAS_LLM = False
    print("[WARN] Could not import LLMClient. Chat will use mock responses.")

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# WebSocket support
try:
    import websockets
    import websockets.sync.server
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("[WARN] websockets not installed. 3D UI won't receive live state.")

# Webcam support
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("[WARN] opencv-python not installed. Camera simulation disabled.")

# Audio support
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    print("[WARN] pyaudio not installed. Mic simulation disabled.")

import subprocess

from sim_state import PepperState


# ─── Global State ──────────────────────────────────────────────────
pepper = PepperState()
ws_clients = set()
webcam = None
audio_stream = None
pa = None

SIM_WEB_PORT = int(os.environ.get("SIM_WEB_PORT", 5002))
SIM_WS_PORT = int(os.environ.get("SIM_WS_PORT", 5003))
SIM_BRIDGE_PORT = int(os.environ.get("SIM_BRIDGE_PORT", 5001))

# ─── LLM Brain ────────────────────────────────────────────────────
BRAIN_URL = os.environ.get("BRAIN_URL", "http://localhost:8090/v1")

brain = None
chat_history: list = []

if HAS_LLM:
    brain = LLMClient(base_url=BRAIN_URL, name="deep", thinking=True, default_max_tokens=2048, timeout=180)
    print(f"[LLM] Brain: {BRAIN_URL}")

# ─── Local TTS (Piper) ───────────────────────────────────────────
PIPER_MODEL = os.path.expanduser("~/models/piper/en_US-amy-medium.onnx")
_tts_process = None

def speak_local(text: str):
    """Generate and play speech with piper TTS in a background thread."""
    global _tts_process
    if _tts_process and _tts_process.poll() is None:
        _tts_process.terminate()
    try:
        _tts_process = subprocess.Popen(
            f'echo {_shell_quote(text)} | piper --model {PIPER_MODEL} --output-raw 2>/dev/null | aplay -r 22050 -f S16_LE -q 2>/dev/null',
            shell=True,
        )
    except Exception as e:
        print(f"[TTS] Piper error: {e}")

def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"

def stop_local_tts():
    global _tts_process
    if _tts_process and _tts_process.poll() is None:
        _tts_process.terminate()


# ─── Webcam Manager ───────────────────────────────────────────────
class WebcamManager:
    """Manages laptop webcam as simulated Pepper camera."""

    def __init__(self):
        self.cap = None
        self.lock = threading.Lock()

    def open(self):
        if HAS_OPENCV and self.cap is None:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("[WARN] Could not open webcam")
                self.cap = None

    def get_frame(self, width=640, height=480):
        """Capture a frame, return as base64 JPEG."""
        with self.lock:
            if self.cap is None or not self.cap.isOpened():
                return self._generate_placeholder(width, height)
            ret, frame = self.cap.read()
            if not ret:
                return self._generate_placeholder(width, height)
            frame = cv2.resize(frame, (width, height))
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return base64.b64encode(jpeg.tobytes()).decode("utf-8")

    def _generate_placeholder(self, width, height):
        """Generate a placeholder image when no webcam available."""
        if HAS_OPENCV:
            import numpy as np
            img = np.zeros((height, width, 3), dtype=np.uint8)
            img[:] = (40, 40, 40)
            cv2.putText(img, "SIMULATOR CAM", (width // 4, height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.putText(img, "No webcam detected", (width // 4, height // 2 + 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
            _, jpeg = cv2.imencode(".jpg", img)
            return base64.b64encode(jpeg.tobytes()).decode("utf-8")
        # Minimal 1x1 black JPEG
        return "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMCwsKCwsM"

    def close(self):
        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None


# ─── Audio Manager ─────────────────────────────────────────────────
class AudioManager:
    """Manages laptop mic as simulated Pepper microphone."""

    def __init__(self):
        self.pa = None
        self.stream = None

    def open(self):
        if HAS_PYAUDIO:
            try:
                self.pa = pyaudio.PyAudio()
                self.stream = self.pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=1024
                )
            except Exception as e:
                print(f"[WARN] Could not open mic: {e}")
                self.stream = None

    def record(self, seconds=5):
        """Record N seconds of audio, return as WAV bytes."""
        if not self.stream:
            return self._generate_silence(seconds)
        frames = []
        num_chunks = int(16000 * seconds / 1024)
        for _ in range(num_chunks):
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                break
        # Pack as WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)
            wf.writeframes(b"".join(frames))
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def get_chunk(self, chunk_size=4096):
        """Get a raw audio chunk for streaming."""
        if not self.stream:
            return base64.b64encode(b"\x00" * chunk_size).decode("utf-8")
        try:
            data = self.stream.read(chunk_size // 2, exception_on_overflow=False)
            return base64.b64encode(data).decode("utf-8")
        except Exception:
            return base64.b64encode(b"\x00" * chunk_size).decode("utf-8")

    def _generate_silence(self, seconds):
        """Generate silent audio when no mic available."""
        num_samples = int(16000 * seconds)
        silence = b"\x00\x00" * num_samples
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(silence)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.pa:
            self.pa.terminate()


# ─── Bridge Request Handler ──────────────────────────────────────
class BridgeHandler(BaseHTTPRequestHandler):
    """
    HTTP handler matching EXACTLY the real Pepper bridge API.
    Every endpoint returns the same JSON structure as the real bridge.
    """

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw": base64.b64encode(body).decode("utf-8")}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging, we use our own
        pass

    # ─── GET routes ──────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        routes = {
            "/health":         self._get_health,
            "/battery":        self._get_battery,
            "/camera/frame":   self._get_camera_frame,
            "/audio/stream":   self._get_audio_stream,
            "/speak/status":   self._get_speak_status,
            "/face/detect":    self._get_face_detect,
            "/animation/list": self._get_animation_list,
            "/navigate/position": self._get_nav_position,
            "/navigate/map":   self._get_nav_map,
            "/posture/current": self._get_current_posture,
            "/joints/angles":  self._get_joint_angles,
        }

        handler = routes.get(path)
        if handler:
            response = handler(params)
            pepper.log_api_call(path, "GET", response=response)
            self._send_json(response)
        else:
            self._send_json({"success": False, "error": f"Unknown endpoint: {path}"}, 404)

    def _get_health(self, params):
        return {
            "success": True,
            "data": {
                "status": "ok",
                "battery": round(pepper.battery, 1),
                "uptime": round(time.time() - pepper.boot_time),
                "simulator": True
            }
        }

    def _get_battery(self, params):
        return {
            "success": True,
            "data": {
                "level": round(pepper.battery, 1),
                "charging": pepper.charging
            }
        }

    def _get_camera_frame(self, params):
        camera = params.get("camera", ["top"])[0]
        width = int(params.get("width", [640])[0])
        height = int(params.get("height", [480])[0])
        frame_b64 = webcam.get_frame(width, height)
        return {
            "success": True,
            "data": {
                "image": frame_b64,
                "width": width,
                "height": height,
                "camera": camera,
                "format": "jpeg",
                "timestamp": time.time()
            }
        }

    def _get_audio_stream(self, params):
        chunk = audio_manager.get_chunk()
        return {
            "success": True,
            "data": {
                "audio": chunk,
                "sample_rate": 16000,
                "channels": 1,
                "format": "int16",
                "timestamp": time.time()
            }
        }

    def _get_speak_status(self, params):
        return {
            "success": True,
            "data": {"is_speaking": pepper.is_speaking}
        }

    def _get_face_detect(self, params):
        # Simulated — returns empty or mock detection
        return {
            "success": True,
            "data": {
                "faces": [],
                "timestamp": time.time()
            }
        }

    def _get_animation_list(self, params):
        return {
            "success": True,
            "data": {"animations": pepper.ANIMATIONS}
        }

    def _get_nav_position(self, params):
        pos = pepper.get_robot_position()
        return {
            "success": True,
            "data": {"x": pos[0], "y": pos[1], "theta": pos[2]}
        }

    def _get_nav_map(self, params):
        return {
            "success": True,
            "data": {
                "has_map": pepper.has_map,
                "grid": pepper.occupancy_grid,
                "resolution": 0.1,
                "width": 8.0,
                "height": 6.0,
                "objects": pepper.ROOM_OBJECTS
            }
        }

    def _get_current_posture(self, params):
        return {
            "success": True,
            "data": {"posture": pepper.posture}
        }

    def _get_joint_angles(self, params):
        names = params.get("names", ["Body"])[0]
        angles = pepper.get_angles(names)
        return {
            "success": True,
            "data": {"names": names, "angles": angles}
        }

    # ─── POST routes ─────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        routes = {
            "/speak":              self._post_speak,
            "/speak/stop":         self._post_speak_stop,
            "/audio/record":       self._post_audio_record,
            "/audio/play":         self._post_audio_play,
            "/move/velocity":      self._post_move_velocity,
            "/move/to":            self._post_move_to,
            "/move/stop":          self._post_move_stop,
            "/posture/set":        self._post_posture_set,
            "/head/set":           self._post_head_set,
            "/joints/set":         self._post_joints_set,
            "/joints/stiffness":   self._post_joints_stiffness,
            "/leds/eyes":          self._post_leds_eyes,
            "/leds/ears":          self._post_leds_ears,
            "/animation/run":      self._post_animation_run,
            "/tablet/show/url":    self._post_tablet_url,
            "/tablet/show/image":  self._post_tablet_image,
            "/tablet/hide":        self._post_tablet_hide,
            "/face/track/start":   self._post_face_track_start,
            "/face/track/stop":    self._post_face_track_stop,
            "/autonomous/set":     self._post_autonomous_set,
            "/awareness/set":      self._post_awareness_set,
            "/navigate/explore":   self._post_nav_explore,
            "/navigate/goto":      self._post_nav_goto,
            "/navigate/save":      self._post_nav_save,
            "/navigate/load":      self._post_nav_load,
            "/chat":               self._post_chat,
            "/search_results":     self._post_search_results,
        }

        handler = routes.get(path)
        if handler:
            response = handler(body)
            pepper.log_api_call(path, "POST", body=body, response=response)
            self._send_json(response)
        else:
            self._send_json({"success": False, "error": f"Unknown endpoint: {path}"}, 404)

    def _post_speak(self, body):
        text = body.get("text", "")
        language = body.get("language", "en")
        speed = body.get("speed", 100)
        pitch = body.get("pitch", 100)
        pepper.say(text, language, speed, pitch)
        speak_local(text)
        def finish():
            if _tts_process:
                _tts_process.wait()
            else:
                time.sleep(max(1.0, len(text.split()) * 0.15 * (100 / speed)))
            pepper.finish_speaking()
        threading.Thread(target=finish, daemon=True).start()
        print(f"[SPEAK] ({language}) {text}")
        return {"success": True, "data": {"duration_estimate": len(text.split()) * 0.15}}

    def _post_speak_stop(self, body):
        pepper.stop_speaking()
        stop_local_tts()
        return {"success": True, "data": {}}

    def _post_audio_record(self, body):
        seconds = body.get("seconds", 5)
        audio_b64 = audio_manager.record(seconds)
        return {
            "success": True,
            "data": {
                "audio": audio_b64,
                "duration": seconds,
                "sample_rate": 16000,
                "format": "wav"
            }
        }

    def _post_audio_play(self, body):
        print(f"[AUDIO PLAY] Playing audio on Pepper speakers")
        return {"success": True, "data": {}}

    def _post_move_velocity(self, body):
        vx = body.get("x", 0)
        vy = body.get("y", 0)
        vtheta = body.get("theta", 0)
        pepper.move_toward(vx, vy, vtheta)
        print(f"[MOVE] velocity x={vx} y={vy} θ={vtheta}")
        return {"success": True, "data": {}}

    def _post_move_to(self, body):
        x = body.get("x", 0)
        y = body.get("y", 0)
        theta = body.get("theta", 0)
        pepper.move_to(x, y, theta)
        print(f"[MOVE] to relative x={x} y={y} θ={theta}")
        return {"success": True, "data": {}}

    def _post_move_stop(self, body):
        pepper.stop_move()
        print("[MOVE] stopped")
        return {"success": True, "data": {}}

    def _post_posture_set(self, body):
        posture = body.get("posture", "StandInit")
        speed = body.get("speed", 0.5)
        result = pepper.go_to_posture(posture, speed)
        print(f"[POSTURE] → {posture}")
        return {"success": result, "data": {"posture": posture}}

    def _post_head_set(self, body):
        yaw = body.get("yaw", 0)
        pitch = body.get("pitch", 0)
        speed = body.get("speed", 0.2)
        pepper.set_angles(["HeadYaw", "HeadPitch"], [yaw, pitch], speed)
        return {"success": True, "data": {"yaw": yaw, "pitch": pitch}}

    def _post_joints_set(self, body):
        names = body.get("names", [])
        angles = body.get("angles", [])
        speed = body.get("speed", 0.2)
        pepper.set_angles(names, angles, speed)
        return {"success": True, "data": {"names": names, "angles": angles}}

    def _post_joints_stiffness(self, body):
        names = body.get("names", "Body")
        values = body.get("values", 1.0)
        pepper.set_stiffnesses(names, values)
        return {"success": True, "data": {}}

    def _post_leds_eyes(self, body):
        r = body.get("r", 255)
        g = body.get("g", 255)
        b = body.get("b", 255)
        pepper.set_eye_color(r, g, b)
        print(f"[LEDS] eyes → rgb({r},{g},{b})")
        return {"success": True, "data": {"r": r, "g": g, "b": b}}

    def _post_leds_ears(self, body):
        intensity = body.get("intensity", 1.0)
        pepper.ear_intensity = intensity
        return {"success": True, "data": {"intensity": intensity}}

    def _post_animation_run(self, body):
        name = body.get("name", "")
        pepper.current_animation = name
        print(f"[ANIMATION] {name}")
        # Clear after 3 seconds
        def clear():
            time.sleep(3)
            pepper.current_animation = None
        threading.Thread(target=clear, daemon=True).start()
        return {"success": True, "data": {"animation": name}}

    def _post_tablet_url(self, body):
        url = body.get("url", "")
        pepper.show_tablet_url(url)
        print(f"[TABLET] showing URL: {url}")
        return {"success": True, "data": {"url": url}}

    def _post_tablet_image(self, body):
        url = body.get("url", "")
        pepper.show_tablet_image(url)
        return {"success": True, "data": {"url": url}}

    def _post_tablet_hide(self, body):
        pepper.hide_tablet()
        return {"success": True, "data": {}}

    def _post_face_track_start(self, body):
        pepper.face_tracking = True
        return {"success": True, "data": {}}

    def _post_face_track_stop(self, body):
        pepper.face_tracking = False
        return {"success": True, "data": {}}

    def _post_autonomous_set(self, body):
        enabled = body.get("enabled", True)
        pepper.autonomous_life = enabled
        return {"success": True, "data": {"enabled": enabled}}

    def _post_awareness_set(self, body):
        enabled = body.get("enabled", True)
        pepper.basic_awareness = enabled
        return {"success": True, "data": {"enabled": enabled}}

    def _post_nav_explore(self, body):
        radius = body.get("radius", 3.0)
        pepper.is_exploring = True
        pepper.has_map = True
        print(f"[NAV] exploring radius={radius}m")
        def finish_explore():
            time.sleep(5)
            pepper.is_exploring = False
        threading.Thread(target=finish_explore, daemon=True).start()
        return {"success": True, "data": {"radius": radius}}

    def _post_nav_goto(self, body):
        x = body.get("x", 0)
        y = body.get("y", 0)
        theta = body.get("theta", 0)
        pepper.navigate_to(x, y, theta)
        print(f"[NAV] goto ({x}, {y}, θ={theta})")
        return {"success": True, "data": {"x": x, "y": y, "theta": theta}}

    def _post_nav_save(self, body):
        pepper.has_map = True
        return {"success": True, "data": {"path": "maps/sim_map.raw"}}

    def _post_nav_load(self, body):
        pepper.has_map = True
        return {"success": True, "data": {}}

    def _post_chat(self, body):
        global chat_history
        text = body.get("text", "")
        if not text:
            return {"success": False, "error": "No text provided"}
        print(f"[CHAT] User: {text}")

        chat_history.append(Message(role="user", content=text))
        if len(chat_history) > 20:
            chat_history = chat_history[-20:]

        response_text, routed_to = self._query_llm(text)

        pepper.say(response_text, "en")
        speak_local(response_text)
        def finish():
            if _tts_process:
                _tts_process.wait()
            else:
                time.sleep(max(1.0, len(response_text.split()) * 0.15))
            pepper.finish_speaking()
        threading.Thread(target=finish, daemon=True).start()

        chat_history.append(Message(role="assistant", content=response_text))

        return {
            "success": True,
            "data": {
                "response": response_text,
                "routed_to": routed_to,
                "tools_used": [],
            }
        }

    def _query_llm(self, text):
        """Try brain → mock fallback."""
        system = "You are Pepper, a friendly humanoid robot. Reply in one or two sentences. Do not assume or invent the user's name unless they told you."
        history = chat_history[:-1] if chat_history else []

        if brain:
            resp = brain.chat(text, system=system, history=history, profile="social", max_tokens=2048, reasoning_budget=512)
            if resp.success and resp.spoken_text:
                print(f"[CHAT] Brain: {resp.spoken_text} ({resp.tok_per_sec:.0f} tok/s)")
                return resp.spoken_text, "deep"
            else:
                print(f"[CHAT] Brain failed: success={resp.success} error={resp.error} content={repr(resp.content)}")

        print("[CHAT] Brain unavailable, using mock response")
        mock_responses = [
            "Hello! I'm running in simulator mode right now.",
            "That's an interesting question! Let me think about it.",
            "I'm Pepper, nice to chat with you!",
            "No LLM brain is reachable. Start it with ./start_dev.sh",
        ]
        idx = int(hashlib.md5(text.encode()).hexdigest(), 16) % len(mock_responses)
        return mock_responses[idx], "mock"

    def _post_search_results(self, body):
        query = body.get("query", "")
        results = body.get("results", [])
        pepper.push_search_result(query, results)
        print(f"[SEARCH] query='{query}' results={len(results)}")
        return {"success": True, "data": {"query": query, "count": len(results)}}


# ─── WebSocket State Broadcaster ────────────────────────────────
async def ws_handler(websocket):
    """Send state updates to 3D frontend every 50ms (20fps)."""
    ws_clients.add(websocket)
    try:
        while True:
            state = pepper.to_dict()
            await websocket.send(json.dumps(state))
            if state.get("search_results"):
                pepper.clear_search_results()
            await asyncio.sleep(0.05)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)


async def start_ws_server():
    """Start the WebSocket server."""
    if not HAS_WEBSOCKETS:
        return
    server = await websockets.serve(ws_handler, "0.0.0.0", SIM_WS_PORT)
    print(f"[WS] State broadcast on ws://localhost:{SIM_WS_PORT}")
    await server.wait_closed()


def run_ws_in_thread():
    """Run WebSocket server in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_ws_server())


# ─── Physics Loop ────────────────────────────────────────────────
def physics_loop():
    """Update physics at 60fps."""
    while True:
        pepper.update(1 / 60)
        time.sleep(1 / 60)


# ─── Main ────────────────────────────────────────────────────────
def main():
    global webcam, audio_manager

    print("=" * 60)
    print("  PEPPER SIMULATOR BRIDGE")
    print("  API-compatible with real Pepper NAOqi bridge")
    print("=" * 60)

    # Initialize hardware proxies
    webcam = WebcamManager()
    webcam.open()

    audio_manager = AudioManager()
    audio_manager.open()

    # Start physics thread
    physics_thread = threading.Thread(target=physics_loop, daemon=True)
    physics_thread.start()
    print("[PHYSICS] Running at 60fps")

    # Start WebSocket broadcast thread
    if HAS_WEBSOCKETS:
        ws_thread = threading.Thread(target=run_ws_in_thread, daemon=True)
        ws_thread.start()

    # Start HTTP bridge server
    server = HTTPServer(("0.0.0.0", SIM_BRIDGE_PORT), BridgeHandler)
    print(f"[BRIDGE] Listening on http://localhost:{SIM_BRIDGE_PORT}")
    print(f"[INFO] Webcam: {'active' if webcam.cap else 'placeholder mode'}")
    print(f"[INFO] Mic: {'active' if audio_manager.stream else 'silent mode'}")
    print()
    print("  Middleware can now connect to this bridge.")
    print("  3D UI should connect to ws://localhost:5003")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Closing simulator...")
        webcam.close()
        audio_manager.close()
        server.server_close()


if __name__ == "__main__":
    main()
