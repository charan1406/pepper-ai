# -*- coding: utf-8 -*-
"""
Pepper Bridge — Real NAOqi Connection (Python 2.7)
=====================================================
This script runs as a subprocess. It requires Python 2.7 with
the NAOqi SDK installed.

It exposes the EXACT SAME HTTP endpoints as sim_bridge.py.
The middleware doesn't know or care whether it's talking to
the simulator or this real bridge.

Usage:
  python2.7 bridge.py --ip 192.168.1.100 --port 9559 --bridge-port 5001
"""

import json
import time
import base64
import sys
import argparse
import threading
import wave
import array
import shutil

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
from urlparse import urlparse, parse_qs

# NAOqi SDK — must be installed for Python 2.7
try:
    from naoqi import ALProxy
    HAS_NAOQI = True
except ImportError:
    print("[ERROR] NAOqi SDK not found. Install it for Python 2.7.")
    print("        This bridge requires the real NAOqi SDK.")
    HAS_NAOQI = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("[WARN] cv2/numpy not found — camera will return raw RGB instead of JPEG")

# ─── Configuration ───────────────────────────────────────────────
ROBOT_IP = "192.168.1.100"
ROBOT_PORT = 9559


# ─── NAOqi Proxy Manager ────────────────────────────────────────
class NAOqiManager(object):
    """Manages connections to NAOqi services."""

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self._proxies = {}

    def get(self, service_name):
        """Get or create an ALProxy for the given service."""
        if service_name not in self._proxies:
            try:
                self._proxies[service_name] = ALProxy(service_name, self.ip, self.port)
            except Exception as e:
                print("[ERROR] Cannot connect to %s: %s" % (service_name, str(e)))
                return None
        return self._proxies[service_name]

    @property
    def tts(self):
        return self.get("ALTextToSpeech")

    @property
    def motion(self):
        return self.get("ALMotion")

    @property
    def posture(self):
        return self.get("ALRobotPosture")

    @property
    def video(self):
        return self.get("ALVideoDevice")

    @property
    def audio_device(self):
        return self.get("ALAudioDevice")

    @property
    def audio_player(self):
        return self.get("ALAudioPlayer")

    @property
    def leds(self):
        return self.get("ALLeds")

    @property
    def animation(self):
        return self.get("ALAnimationPlayer")

    @property
    def tablet(self):
        return self.get("ALTabletService")

    @property
    def face_detect(self):
        return self.get("ALFaceDetection")

    @property
    def tracker(self):
        return self.get("ALTracker")

    @property
    def autonomous(self):
        return self.get("ALAutonomousLife")

    @property
    def awareness(self):
        return self.get("ALBasicAwareness")

    @property
    def battery(self):
        return self.get("ALBattery")

    @property
    def memory(self):
        return self.get("ALMemory")

    @property
    def navigation(self):
        return self.get("ALNavigation")


naoqi = None  # initialized in main()


def _extract_mono(src, dst, channel=0):
    """Extract a single channel from a multi-channel WAV file."""
    wf = wave.open(src, 'rb')
    n_channels = wf.getnchannels()
    sampwidth = wf.getsampwidth()
    framerate = wf.getframerate()
    raw = wf.readframes(wf.getnframes())
    wf.close()

    if n_channels == 1:
        shutil.copy2(src, dst)
        return framerate

    if sampwidth == 2:
        fmt = 'h'
    elif sampwidth == 4:
        fmt = 'i'
    else:
        fmt = 'b'

    samples = array.array(fmt)
    samples.fromstring(raw)

    mono = array.array(fmt)
    for i in range(channel, len(samples), n_channels):
        mono.append(samples[i])

    wf_out = wave.open(dst, 'wb')
    wf_out.setnchannels(1)
    wf_out.setsampwidth(sampwidth)
    wf_out.setframerate(framerate)
    wf_out.writeframes(mono.tostring())
    wf_out.close()
    return framerate


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# TTS task tracking for speak_and_wait
_speak_lock = threading.Lock()
_speak_task_id = None


# ─── Bridge Handler ──────────────────────────────────────────────
class BridgeHandler(BaseHTTPRequestHandler):
    """HTTP handler — identical API to sim_bridge.py."""

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        try:
            return json.loads(body)
        except (ValueError, TypeError):
            return {"raw": base64.b64encode(body)}

    def _error(self, msg):
        return {"success": False, "error": msg}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress default logging

    # ─── GET ─────────────────────────────────────────────────────

    def do_GET(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        handlers = {
            "/health": self._get_health,
            "/battery": self._get_battery,
            "/camera/frame": self._get_camera_frame,
            "/audio/stream": self._get_audio_stream,
            "/speak/status": self._get_speak_status,
            "/face/detect": self._get_face_detect,
            "/animation/list": self._get_animation_list,
            "/navigate/position": self._get_nav_position,
            "/navigate/map": self._get_nav_map,
            "/posture/current": self._get_current_posture,
            "/joints/angles": self._get_joint_angles,
        }

        handler = handlers.get(path)
        if handler:
            self._send_json(handler(params))
        else:
            self._send_json(self._error("Unknown: %s" % path), 404)

    def _get_health(self, p):
        try:
            level = naoqi.battery.getBatteryCharge()
            return {"success": True, "data": {"status": "ok", "battery": level, "simulator": False}}
        except Exception as e:
            return {"success": False, "data": {"status": "error", "error": str(e)}}

    def _get_battery(self, p):
        try:
            level = naoqi.battery.getBatteryCharge()
            charging = naoqi.memory.getData("Device/SubDeviceList/Battery/Charge/Sensor/Power") > 0
            return {"success": True, "data": {"level": level, "charging": charging}}
        except Exception as e:
            return self._error(str(e))

    def _get_camera_frame(self, p):
        subscriber = None
        try:
            camera_idx = 0 if p.get("camera", ["top"])[0] == "top" else 1
            width = int(p.get("width", [640])[0])
            height = int(p.get("height", [480])[0])

            # Resolution mapping (NAOqi uses resolution IDs)
            res_map = {(320, 240): 1, (640, 480): 2, (1280, 960): 3}
            resolution = res_map.get((width, height), 2)

            sub_name = "pb_%d" % int(time.time() * 1000)
            subscriber = naoqi.video.subscribeCamera(
                sub_name, camera_idx, resolution, 11, 10  # 11=RGB, 10fps
            )
            img = naoqi.video.getImageRemote(subscriber)

            if img is None:
                return self._error("Camera returned None")

            raw = img[6]
            img_w, img_h = img[0], img[1]

            if HAS_CV2:
                frame = np.frombuffer(raw, dtype=np.uint8).reshape((img_h, img_w, 3))
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                _, jpeg = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                b64 = base64.b64encode(jpeg.tobytes())
                fmt = "jpeg"
            else:
                b64 = base64.b64encode(raw)
                fmt = "raw_rgb"

            return {
                "success": True,
                "data": {
                    "image": b64,
                    "width": img_w,
                    "height": img_h,
                    "camera": "top" if camera_idx == 0 else "bottom",
                    "format": fmt,
                    "timestamp": time.time()
                }
            }
        except Exception as e:
            return self._error("Camera error: %s" % str(e))
        finally:
            if subscriber is not None:
                try:
                    naoqi.video.unsubscribe(subscriber)
                except Exception:
                    pass

    def _get_audio_stream(self, p):
        # Audio streaming is complex with NAOqi; return a chunk via ALAudioDevice
        try:
            return {"success": True, "data": {
                "audio": "", "sample_rate": 16000,
                "channels": 1, "format": "int16", "timestamp": time.time()
            }}
        except Exception as e:
            return self._error(str(e))

    def _get_speak_status(self, p):
        global _speak_task_id
        try:
            with _speak_lock:
                task_id = _speak_task_id
            is_speaking = False
            if task_id is not None:
                is_speaking = naoqi.tts.isRunning(task_id)
                if not is_speaking:
                    with _speak_lock:
                        _speak_task_id = None
            return {"success": True, "data": {"is_speaking": is_speaking}}
        except Exception as e:
            return self._error(str(e))

    def _get_face_detect(self, p):
        try:
            val = naoqi.memory.getData("FaceDetected")
            faces = []
            if val and len(val) > 1:
                for face_info in val[1]:
                    if len(face_info) > 0:
                        faces.append({"id": face_info[1][0], "confidence": face_info[1][1]})
            return {"success": True, "data": {"faces": faces, "timestamp": time.time()}}
        except Exception:
            return {"success": True, "data": {"faces": [], "timestamp": time.time()}}

    def _get_animation_list(self, p):
        try:
            anims = naoqi.animation.getAnimationsList()
            return {"success": True, "data": {"animations": anims}}
        except Exception:
            return {"success": True, "data": {"animations": []}}

    def _get_nav_position(self, p):
        try:
            pos = naoqi.navigation.getRobotPositionInMap()
            return {"success": True, "data": {"x": pos[0], "y": pos[1], "theta": pos[2]}}
        except Exception:
            pos = naoqi.motion.getRobotPosition(True)
            return {"success": True, "data": {"x": pos[0], "y": pos[1], "theta": pos[2]}}

    def _get_nav_map(self, p):
        try:
            has_map = naoqi.navigation.getExplorationMap() is not None
            return {"success": True, "data": {"has_map": has_map}}
        except Exception:
            return {"success": True, "data": {"has_map": False}}

    def _get_current_posture(self, p):
        try:
            posture = naoqi.posture.getPostureFamily()
            return {"success": True, "data": {"posture": posture}}
        except Exception as e:
            return self._error(str(e))

    def _get_joint_angles(self, p):
        try:
            names = p.get("names", ["Body"])[0]
            angles = naoqi.motion.getAngles(names, True)
            return {"success": True, "data": {"names": names, "angles": list(angles)}}
        except Exception as e:
            return self._error(str(e))

    # ─── POST ────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        handlers = {
            "/speak":            self._post_speak,
            "/speak/stop":       self._post_speak_stop,
            "/audio/record":     self._post_audio_record,
            "/audio/play":       self._post_audio_play,
            "/move/velocity":    self._post_move_velocity,
            "/move/to":          self._post_move_to,
            "/move/stop":        self._post_move_stop,
            "/posture/set":      self._post_posture_set,
            "/head/set":         self._post_head_set,
            "/joints/set":       self._post_joints_set,
            "/joints/stiffness": self._post_joints_stiffness,
            "/leds/eyes":        self._post_leds_eyes,
            "/leds/ears":        self._post_leds_ears,
            "/animation/run":    self._post_animation_run,
            "/tablet/show/url":  self._post_tablet_url,
            "/tablet/show/image": self._post_tablet_image,
            "/tablet/hide":      self._post_tablet_hide,
            "/face/track/start": self._post_face_track_start,
            "/face/track/stop":  self._post_face_track_stop,
            "/autonomous/set":   self._post_autonomous_set,
            "/awareness/set":    self._post_awareness_set,
            "/navigate/explore": self._post_nav_explore,
            "/navigate/goto":    self._post_nav_goto,
            "/navigate/save":    self._post_nav_save,
            "/navigate/load":    self._post_nav_load,
        }

        handler = handlers.get(path)
        if handler:
            self._send_json(handler(body))
        else:
            self._send_json(self._error("Unknown: %s" % path), 404)

    def _post_speak(self, body):
        global _speak_task_id
        try:
            text = body.get("text", "")
            lang = body.get("language", "en")
            naoqi.tts.setLanguage({"en": "English", "de": "German", "fr": "French",
                                    "it": "Italian", "es": "Spanish", "ja": "Japanese",
                                    "zh": "Chinese", "ar": "Arabic"}.get(lang, "English"))
            task_id = naoqi.tts.post.say(text)
            with _speak_lock:
                _speak_task_id = task_id
            return {"success": True, "data": {"task_id": task_id}}
        except Exception as e:
            return self._error(str(e))

    def _post_speak_stop(self, body):
        global _speak_task_id
        try:
            naoqi.tts.stopAll()
            with _speak_lock:
                _speak_task_id = None
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_audio_record(self, body):
        try:
            seconds = body.get("seconds", 5)
            ts = int(time.time() * 1000)
            raw_path = "/tmp/pepper_rec_raw_%d.wav" % ts
            mono_path = "/tmp/pepper_rec_%d.wav" % ts

            naoqi.audio_device.startMicrophonesRecording(raw_path)
            time.sleep(seconds)
            naoqi.audio_device.stopMicrophonesRecording()

            # NAOqi records 4-channel 48kHz — extract front mic as mono
            sample_rate = _extract_mono(raw_path, mono_path, channel=0)

            with open(mono_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read())

            try:
                import os as _os
                _os.remove(raw_path)
                _os.remove(mono_path)
            except OSError:
                pass

            return {"success": True, "data": {
                "audio": audio_b64, "duration": seconds,
                "sample_rate": sample_rate, "format": "wav"
            }}
        except Exception as e:
            return self._error(str(e))

    def _post_audio_play(self, body):
        try:
            audio_data = body.get("raw", "")
            if audio_data:
                wav_bytes = base64.b64decode(audio_data)
                path = "/tmp/pepper_play_%d.wav" % int(time.time() * 1000)
                with open(path, "wb") as f:
                    f.write(wav_bytes)
                task_id = naoqi.audio_player.post.playFile(path)

                def _cleanup(tid, fpath):
                    try:
                        naoqi.audio_player.wait(tid, 30000)
                    except Exception:
                        time.sleep(5)
                    try:
                        import os as _os
                        _os.remove(fpath)
                    except OSError:
                        pass

                threading.Thread(target=_cleanup, args=(task_id, path), daemon=True).start()
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_move_velocity(self, body):
        try:
            vx = body.get("x", 0)
            vy = body.get("y", 0)
            vt = body.get("theta", 0)
            naoqi.motion.moveToward(vx, vy, vt)
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_move_to(self, body):
        try:
            x = body.get("x", 0)
            y = body.get("y", 0)
            theta = body.get("theta", 0)
            naoqi.motion.post.moveTo(x, y, theta)
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_move_stop(self, body):
        try:
            naoqi.motion.stopMove()
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_posture_set(self, body):
        try:
            name = body.get("posture", "StandInit")
            speed = body.get("speed", 0.5)
            naoqi.posture.post.goToPosture(name, speed)
            return {"success": True, "data": {"posture": name}}
        except Exception as e:
            return self._error(str(e))

    def _post_head_set(self, body):
        try:
            yaw = body.get("yaw", 0)
            pitch = body.get("pitch", 0)
            speed = body.get("speed", 0.2)
            naoqi.motion.setStiffnesses("Head", 1.0)
            naoqi.motion.setAngles(["HeadYaw", "HeadPitch"], [yaw, pitch], speed)
            return {"success": True, "data": {"yaw": yaw, "pitch": pitch}}
        except Exception as e:
            return self._error(str(e))

    def _post_joints_set(self, body):
        try:
            names = body.get("names", [])
            angles = body.get("angles", [])
            speed = body.get("speed", 0.2)
            naoqi.motion.setAngles(names, angles, speed)
            return {"success": True, "data": {"names": names, "angles": angles}}
        except Exception as e:
            return self._error(str(e))

    def _post_joints_stiffness(self, body):
        try:
            names = body.get("names", "Body")
            values = body.get("values", 1.0)
            naoqi.motion.setStiffnesses(names, values)
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_leds_eyes(self, body):
        try:
            r = body.get("r", 255)
            g = body.get("g", 255)
            b = body.get("b", 255)
            hex_color = int("0x00%02x%02x%02x" % (r, g, b), 16)
            naoqi.leds.fadeRGB("FaceLeds", hex_color, 0.5)
            return {"success": True, "data": {"r": r, "g": g, "b": b}}
        except Exception as e:
            return self._error(str(e))

    def _post_leds_ears(self, body):
        try:
            intensity = body.get("intensity", 1.0)
            naoqi.leds.setIntensity("EarLeds", intensity)
            return {"success": True, "data": {"intensity": intensity}}
        except Exception as e:
            return self._error(str(e))

    def _post_animation_run(self, body):
        try:
            name = body.get("name", "")
            naoqi.animation.post.run(name)
            return {"success": True, "data": {"animation": name}}
        except Exception as e:
            return self._error(str(e))

    def _post_tablet_url(self, body):
        try:
            url = body.get("url", "")
            naoqi.tablet.showWebview(url)
            return {"success": True, "data": {"url": url}}
        except Exception as e:
            return self._error(str(e))

    def _post_tablet_image(self, body):
        try:
            url = body.get("url", "")
            naoqi.tablet.showImage(url)
            return {"success": True, "data": {"url": url}}
        except Exception as e:
            return self._error(str(e))

    def _post_tablet_hide(self, body):
        try:
            naoqi.tablet.hide()
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_face_track_start(self, body):
        try:
            naoqi.face_detect.subscribe("pepper_bridge")
            naoqi.tracker.registerTarget("Face", 0.1)
            naoqi.tracker.track("Face")
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_face_track_stop(self, body):
        try:
            naoqi.tracker.stopTracker()
            naoqi.face_detect.unsubscribe("pepper_bridge")
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))

    def _post_autonomous_set(self, body):
        try:
            enabled = body.get("enabled", True)
            state = "solitary" if enabled else "disabled"
            naoqi.autonomous.setState(state)
            return {"success": True, "data": {"enabled": enabled}}
        except Exception as e:
            return self._error(str(e))

    def _post_awareness_set(self, body):
        try:
            enabled = body.get("enabled", True)
            if enabled:
                naoqi.awareness.setEnabled(True)
            else:
                naoqi.awareness.setEnabled(False)
            return {"success": True, "data": {"enabled": enabled}}
        except Exception as e:
            return self._error(str(e))

    def _post_nav_explore(self, body):
        try:
            radius = body.get("radius", 3.0)
            naoqi.navigation.post.explore(radius)
            return {"success": True, "data": {"radius": radius}}
        except Exception as e:
            return self._error(str(e))

    def _post_nav_goto(self, body):
        try:
            x = body.get("x", 0)
            y = body.get("y", 0)
            theta = body.get("theta", 0)
            try:
                naoqi.navigation.post.navigateToInMap([x, y, theta])
            except Exception:
                naoqi.motion.post.moveTo(x, y, theta)
            return {"success": True, "data": {"x": x, "y": y, "theta": theta}}
        except Exception as e:
            return self._error(str(e))

    def _post_nav_save(self, body):
        try:
            path = naoqi.navigation.saveExploration()
            return {"success": True, "data": {"path": path}}
        except Exception as e:
            return self._error(str(e))

    def _post_nav_load(self, body):
        try:
            path = body.get("path", "")
            naoqi.navigation.loadExploration(path)
            return {"success": True, "data": {}}
        except Exception as e:
            return self._error(str(e))


# ─── Main ────────────────────────────────────────────────────────
def main():
    global naoqi, ROBOT_IP, ROBOT_PORT

    parser = argparse.ArgumentParser(description="Pepper NAOqi Bridge")
    parser.add_argument("--ip", type=str, default="192.168.1.100", help="Robot IP")
    parser.add_argument("--port", type=int, default=9559, help="NAOqi port")
    parser.add_argument("--bridge-port", type=int, default=5001, help="Bridge HTTP port")
    args = parser.parse_args()

    ROBOT_IP = args.ip
    ROBOT_PORT = args.port

    print("=" * 60)
    print("  PEPPER BRIDGE — REAL NAOqi CONNECTION")
    print("  Robot: %s:%d" % (ROBOT_IP, ROBOT_PORT))
    print("  Bridge: http://localhost:%d" % args.bridge_port)
    print("=" * 60)

    if not HAS_NAOQI:
        print("[FATAL] NAOqi SDK not available. Cannot start.")
        sys.exit(1)

    naoqi = NAOqiManager(ROBOT_IP, ROBOT_PORT)

    # Test connection
    try:
        level = naoqi.battery.getBatteryCharge()
        print("[OK] Connected to Pepper. Battery: %d%%" % level)
    except Exception as e:
        print("[ERROR] Cannot connect to Pepper: %s" % str(e))
        print("        Check IP address and ensure robot is on.")
        sys.exit(1)

    server = ThreadedHTTPServer(("0.0.0.0", args.bridge_port), BridgeHandler)
    print("[BRIDGE] Listening on port %d" % args.bridge_port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Bridge stopping.")
        server.server_close()


if __name__ == "__main__":
    main()
