"""
Pepper Bridge Client
=====================
Python 3 HTTP client for the Pepper bridge (simulator or real).
Every method maps 1:1 to a bridge endpoint.

Usage:
    from pepper.client import PepperClient
    pepper = PepperClient("http://localhost:5001")
    pepper.speak("Hello!", language="en")
    frame = pepper.get_camera_frame()
    pepper.move_to(1.0, 0, 0)
"""

import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple, List


class PepperClient:
    """HTTP client for the Pepper bridge server."""

    def __init__(self, bridge_url: str = "http://localhost:5001", timeout: int = 30):
        self.bridge_url = bridge_url.rstrip("/")
        self.timeout = timeout

    # ─── Internal helpers ────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Make a GET request to the bridge."""
        url = f"{self.bridge_url}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url += f"?{query}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"success": False, "error": f"Connection failed: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _post(self, path: str, body: Optional[Dict] = None) -> Dict:
        """Make a POST request to the bridge."""
        url = f"{self.bridge_url}{path}"
        data = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {"success": False, "error": f"Connection failed: {e}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ok(self, response: Dict) -> bool:
        """Check if a response was successful."""
        return response.get("success", False)

    # ─── Health & Status ─────────────────────────────────────────

    def health(self) -> Dict:
        """Check bridge + robot health."""
        return self._get("/health")

    def is_alive(self) -> bool:
        """Quick check: is the bridge responding?"""
        resp = self.health()
        return self._ok(resp)

    def battery(self) -> Dict:
        """Get battery level and charging status."""
        resp = self._get("/battery")
        if self._ok(resp):
            return resp["data"]
        return {"level": -1, "charging": False}

    # ─── Speech ──────────────────────────────────────────────────

    def speak(self, text: str, language: str = "en",
              speed: int = 100, pitch: int = 100) -> bool:
        """Make Pepper speak. Non-blocking (returns immediately)."""
        resp = self._post("/speak", {
            "text": text,
            "language": language,
            "speed": speed,
            "pitch": pitch,
        })
        return self._ok(resp)

    def stop_speaking(self) -> bool:
        """Stop current speech."""
        return self._ok(self._post("/speak/stop"))

    def is_speaking(self) -> bool:
        """Check if Pepper is currently speaking."""
        resp = self._get("/speak/status")
        if self._ok(resp):
            return resp["data"]["is_speaking"]
        return False

    def speak_and_wait(self, text: str, language: str = "en",
                       speed: int = 100, pitch: int = 100,
                       poll_interval: float = 0.2) -> bool:
        """Speak and block until finished."""
        self.speak(text, language, speed, pitch)
        time.sleep(0.3)  # brief delay before polling
        while self.is_speaking():
            time.sleep(poll_interval)
        return True

    # ─── Audio ───────────────────────────────────────────────────

    def play_audio(self, wav_bytes: bytes) -> bool:
        """Play audio through Pepper's speakers (for non-native TTS)."""
        import base64
        resp = self._post("/audio/play", {
            "raw": base64.b64encode(wav_bytes).decode("utf-8")
        })
        return self._ok(resp)

    def record_audio(self, seconds: float = 5) -> Optional[str]:
        """Record audio from Pepper's mic. Returns base64 WAV."""
        resp = self._post("/audio/record", {"seconds": seconds})
        if self._ok(resp):
            return resp["data"]["audio"]
        return None

    def get_audio_chunk(self) -> Optional[str]:
        """Get a single audio chunk from the mic stream. Returns base64 raw audio."""
        resp = self._get("/audio/stream")
        if self._ok(resp):
            return resp["data"]["audio"]
        return None

    # ─── Camera ──────────────────────────────────────────────────

    def get_camera_frame(self, camera: str = "top",
                         width: int = 640, height: int = 480) -> Optional[str]:
        """Get a camera frame as base64 JPEG."""
        resp = self._get("/camera/frame", {
            "camera": camera,
            "width": width,
            "height": height,
        })
        if self._ok(resp):
            return resp["data"]["image"]
        return None

    def get_camera_frame_bytes(self, camera: str = "top",
                                width: int = 640, height: int = 480) -> Optional[bytes]:
        """Get a camera frame as raw JPEG bytes."""
        import base64
        b64 = self.get_camera_frame(camera, width, height)
        if b64:
            return base64.b64decode(b64)
        return None

    # ─── Movement ────────────────────────────────────────────────

    def move_to(self, x: float, y: float = 0, theta: float = 0) -> bool:
        """Move to relative position (meters, radians). Non-blocking."""
        return self._ok(self._post("/move/to", {"x": x, "y": y, "theta": theta}))

    def move_velocity(self, vx: float, vy: float = 0, vtheta: float = 0) -> bool:
        """Set movement velocity (-1 to 1 normalized). Non-blocking."""
        return self._ok(self._post("/move/velocity", {"x": vx, "y": vy, "theta": vtheta}))

    def stop_moving(self) -> bool:
        """Stop all movement."""
        return self._ok(self._post("/move/stop"))

    # ─── Head ────────────────────────────────────────────────────

    def set_head(self, yaw: float = 0, pitch: float = 0, speed: float = 0.2) -> bool:
        """Set head angles (radians). Yaw: left(+)/right(-). Pitch: up(-)/down(+)."""
        return self._ok(self._post("/head/set", {"yaw": yaw, "pitch": pitch, "speed": speed}))

    def look_left(self, angle: float = 0.8) -> bool:
        return self.set_head(yaw=angle)

    def look_right(self, angle: float = 0.8) -> bool:
        return self.set_head(yaw=-angle)

    def look_up(self, angle: float = 0.4) -> bool:
        return self.set_head(pitch=-angle)

    def look_down(self, angle: float = 0.4) -> bool:
        return self.set_head(pitch=angle)

    def look_center(self) -> bool:
        return self.set_head(yaw=0, pitch=0)

    # ─── Joints ──────────────────────────────────────────────────

    def set_joints(self, names: List[str], angles: List[float],
                   speed: float = 0.2) -> bool:
        """Set arbitrary joint angles."""
        return self._ok(self._post("/joints/set", {
            "names": names, "angles": angles, "speed": speed
        }))

    def set_stiffness(self, names: str = "Body", values: float = 1.0) -> bool:
        """Set joint stiffness. Use 'Body', 'Head', 'Arms', 'Legs' or specific joints."""
        return self._ok(self._post("/joints/stiffness", {
            "names": names, "values": values
        }))

    # ─── Posture ─────────────────────────────────────────────────

    def set_posture(self, posture: str = "StandInit", speed: float = 0.5) -> bool:
        """Set a named posture: Stand, StandInit, Crouch, Sit, etc."""
        return self._ok(self._post("/posture/set", {"posture": posture, "speed": speed}))

    def get_posture(self) -> str:
        """Get current posture name."""
        resp = self._get("/posture/current")
        if self._ok(resp):
            return resp["data"]["posture"]
        return "Unknown"

    # ─── LEDs ────────────────────────────────────────────────────

    def set_eye_color(self, r: int = 255, g: int = 255, b: int = 255) -> bool:
        """Set eye LED color (0-255 per channel)."""
        return self._ok(self._post("/leds/eyes", {"r": r, "g": g, "b": b}))

    def eyes_blue(self) -> bool:
        return self.set_eye_color(0, 100, 255)

    def eyes_green(self) -> bool:
        return self.set_eye_color(0, 255, 100)

    def eyes_red(self) -> bool:
        return self.set_eye_color(255, 50, 0)

    def eyes_white(self) -> bool:
        return self.set_eye_color(255, 255, 255)

    def eyes_thinking(self) -> bool:
        """Cyan — indicates Pepper is processing."""
        return self.set_eye_color(0, 200, 255)

    def eyes_listening(self) -> bool:
        """Soft blue — indicates Pepper is listening."""
        return self.set_eye_color(50, 120, 255)

    def eyes_speaking(self) -> bool:
        """Green — indicates Pepper is speaking."""
        return self.set_eye_color(0, 255, 150)

    # ─── Animation ───────────────────────────────────────────────

    def run_animation(self, name: str) -> bool:
        """Run a named animation."""
        return self._ok(self._post("/animation/run", {"name": name}))

    def list_animations(self) -> List[str]:
        """Get available animation names."""
        resp = self._get("/animation/list")
        if self._ok(resp):
            return resp["data"]["animations"]
        return []

    def wave(self) -> bool:
        return self.run_animation("animations/Stand/Gestures/Hey_1")

    def nod_yes(self) -> bool:
        return self.run_animation("animations/Stand/Gestures/Yes_1")

    def shake_no(self) -> bool:
        return self.run_animation("animations/Stand/Gestures/No_1")

    def think_gesture(self) -> bool:
        return self.run_animation("animations/Stand/Gestures/Think_1")

    def bow(self) -> bool:
        return self.run_animation("animations/Stand/Gestures/BowShort_1")

    # ─── Tablet ──────────────────────────────────────────────────

    def tablet_show_url(self, url: str) -> bool:
        """Show a URL on Pepper's chest tablet."""
        return self._ok(self._post("/tablet/show/url", {"url": url}))

    def tablet_show_image(self, url: str) -> bool:
        """Show an image on the tablet."""
        return self._ok(self._post("/tablet/show/image", {"url": url}))

    def tablet_hide(self) -> bool:
        """Hide the tablet display."""
        return self._ok(self._post("/tablet/hide"))

    # ─── Face Detection & Tracking ───────────────────────────────

    def detect_faces(self) -> List[Dict]:
        """Get currently detected faces from Pepper's built-in detection."""
        resp = self._get("/face/detect")
        if self._ok(resp):
            return resp["data"]["faces"]
        return []

    def start_face_tracking(self) -> bool:
        """Start autonomous face tracking (head follows faces)."""
        return self._ok(self._post("/face/track/start"))

    def stop_face_tracking(self) -> bool:
        return self._ok(self._post("/face/track/stop"))

    # ─── Autonomous Life ─────────────────────────────────────────

    def set_autonomous_life(self, enabled: bool = True) -> bool:
        return self._ok(self._post("/autonomous/set", {"enabled": enabled}))

    def set_awareness(self, enabled: bool = True) -> bool:
        return self._ok(self._post("/awareness/set", {"enabled": enabled}))

    # ─── Navigation ──────────────────────────────────────────────

    def get_position(self) -> Tuple[float, float, float]:
        """Get current (x, y, theta) position in map frame."""
        resp = self._get("/navigate/position")
        if self._ok(resp):
            d = resp["data"]
            return (d["x"], d["y"], d["theta"])
        return (0, 0, 0)

    def navigate_to(self, x: float, y: float, theta: float = 0) -> bool:
        """Navigate to absolute map position."""
        return self._ok(self._post("/navigate/goto", {"x": x, "y": y, "theta": theta}))

    def explore(self, radius: float = 3.0) -> bool:
        """Start SLAM exploration."""
        return self._ok(self._post("/navigate/explore", {"radius": radius}))

    def save_map(self) -> bool:
        """Save exploration map."""
        return self._ok(self._post("/navigate/save"))

    def get_map(self) -> Optional[Dict]:
        """Get occupancy grid and room objects."""
        resp = self._get("/navigate/map")
        if self._ok(resp):
            return resp["data"]
        return None
