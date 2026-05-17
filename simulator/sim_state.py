"""
Pepper Simulator — State Engine
=================================
Tracks all state of the simulated Pepper robot: position, joints,
battery, LEDs, speech, posture, tablet, and navigation map.
This state is broadcast to the 3D web frontend via WebSocket.

All movement and joint changes interpolate smoothly at realistic speeds.
"""

import time
import math
import json
import threading


class PepperState:
    """Complete simulated state of a Pepper 1.8 robot."""

    # Joint limits in radians (from NAOqi 2.5 documentation)
    JOINT_LIMITS = {
        "HeadYaw":        (-2.0857, 2.0857),
        "HeadPitch":      (-0.7068, 0.6371),
        "LShoulderPitch": (-2.0857, 2.0857),
        "LShoulderRoll":  (0.0087, 1.5621),
        "LElbowYaw":      (-2.0857, 2.0857),
        "LElbowRoll":     (-1.5621, -0.0087),
        "LWristYaw":      (-1.8239, 1.8239),
        "LHand":          (0.0, 1.0),
        "RShoulderPitch": (-2.0857, 2.0857),
        "RShoulderRoll":  (-1.5621, -0.0087),
        "RElbowYaw":      (-2.0857, 2.0857),
        "RElbowRoll":     (0.0087, 1.5621),
        "RWristYaw":      (-1.8239, 1.8239),
        "RHand":          (0.0, 1.0),
        "HipRoll":        (-0.5149, 0.5149),
        "HipPitch":       (-1.0385, 1.0385),
        "KneePitch":      (-0.5149, 0.5149),
    }

    POSTURES = [
        "Stand", "StandInit", "StandZero",
        "Crouch", "Sit", "SitRelax",
        "LyingBelly", "LyingBack"
    ]

    POSTURE_ANGLES = {
        "Stand": {
            "HeadYaw": 0, "HeadPitch": -0.1,
            "LShoulderPitch": 1.4, "LShoulderRoll": 0.15,
            "LElbowYaw": -1.2, "LElbowRoll": -0.52,
            "RShoulderPitch": 1.4, "RShoulderRoll": -0.15,
            "RElbowYaw": 1.2, "RElbowRoll": 0.52,
            "HipRoll": 0, "HipPitch": 0, "KneePitch": 0,
        },
        "StandInit": {
            "HeadYaw": 0, "HeadPitch": 0,
            "LShoulderPitch": 1.6, "LShoulderRoll": 0.14,
            "LElbowYaw": -1.2, "LElbowRoll": -0.52,
            "RShoulderPitch": 1.6, "RShoulderRoll": -0.14,
            "RElbowYaw": 1.2, "RElbowRoll": 0.52,
            "HipRoll": 0, "HipPitch": -0.03, "KneePitch": 0,
        },
        "Crouch": {
            "HeadYaw": 0, "HeadPitch": 0,
            "LShoulderPitch": 0.1, "LShoulderRoll": 0.1,
            "LElbowYaw": -0.5, "LElbowRoll": -1.0,
            "RShoulderPitch": 0.1, "RShoulderRoll": -0.1,
            "RElbowYaw": 0.5, "RElbowRoll": 1.0,
            "HipRoll": 0, "HipPitch": -0.8, "KneePitch": -0.4,
        },
    }

    ANIMATIONS = [
        "animations/Stand/Gestures/Hey_1",
        "animations/Stand/Gestures/Yes_1",
        "animations/Stand/Gestures/No_1",
        "animations/Stand/Gestures/BowShort_1",
        "animations/Stand/Gestures/Enthusiastic_4",
        "animations/Stand/Gestures/Explain_1",
        "animations/Stand/Gestures/ShowSky_1",
        "animations/Stand/Gestures/Think_1",
        "animations/Stand/Emotions/Positive/Happy_4",
        "animations/Stand/Emotions/Negative/Sad_1",
        "animations/Stand/Waiting/PlayHands_1",
        "animations/Stand/Waiting/LookHand_1",
    ]

    ROOM_OBJECTS = {
        "entrance":        {"x": 0.0, "y": 0.0, "type": "door"},
        "coffee_machine":  {"x": 0.5, "y": 5.0, "type": "appliance"},
        "whiteboard":      {"x": 4.0, "y": 5.5, "type": "furniture"},
        "meeting_table":   {"x": 3.0, "y": 3.0, "type": "furniture"},
        "desk_john":       {"x": 6.5, "y": 1.5, "type": "desk"},
        "desk_priya":      {"x": 1.0, "y": 3.0, "type": "desk"},
        "desk_3":          {"x": 6.5, "y": 4.0, "type": "desk"},
        "fanuc_arm":       {"x": 7.0, "y": 0.5, "type": "equipment"},
        "charging_station": {"x": 0.5, "y": 0.5, "type": "charger"},
    }

    # Physics constants
    MAX_MOVE_SPEED = 0.35       # m/s — real Pepper max
    MAX_ROTATION_SPEED = 1.0    # rad/s
    JOINT_SPEED = 2.0           # rad/s — joint interpolation speed
    ARRIVE_THRESHOLD = 0.02     # meters — close enough to target
    ANGLE_THRESHOLD = 0.01      # radians — close enough for joints

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        """Reset to initial power-on state."""
        with self._lock:
            # Position & orientation in room (meters, radians)
            self.x = 0.5
            self.y = 0.5
            self.theta = 0.0

            # Movement target (None = no active move_to)
            self._move_target = None    # {"x": float, "y": float, "theta": float}

            # Velocity mode (move_toward)
            self.vx = 0.0
            self.vy = 0.0
            self.vtheta = 0.0
            self._velocity_mode = False

            self.is_moving = False

            # Joint angles (radians) — current actual position
            self.joints = {name: 0.0 for name in self.JOINT_LIMITS}
            # Joint targets — where joints are moving toward
            self._joint_targets = {name: 0.0 for name in self.JOINT_LIMITS}
            self._joint_speeds = {name: 0.2 for name in self.JOINT_LIMITS}

            # Apply StandInit pose immediately on boot
            for joint, angle in self.POSTURE_ANGLES.get("StandInit", {}).items():
                if joint in self.joints:
                    self.joints[joint] = angle
                    self._joint_targets[joint] = angle

            # Joint stiffnesses
            self.stiffnesses = {name: 0.0 for name in self.JOINT_LIMITS}

            # Posture
            self.posture = "StandInit"

            # Battery
            self.battery = 100.0
            self.charging = False

            # LEDs
            self.eye_color = {"r": 255, "g": 255, "b": 255}
            self.ear_intensity = 1.0

            # Speech
            self.is_speaking = False
            self.current_speech = ""
            self.speech_language = "en"
            self.speech_speed = 100
            self.speech_pitch = 100

            # Tablet
            self.tablet_url = ""
            self.tablet_visible = False
            self.tablet_image = ""

            # Autonomous life
            self.autonomous_life = True
            self.basic_awareness = True
            self.face_tracking = False

            # Navigation
            self.has_map = False
            self.map_data = None
            self.is_exploring = False
            self.nav_target = None
            self.occupancy_grid = self._generate_default_grid()

            # Timing
            self.boot_time = time.time()
            self.last_update = time.time()

            # API log
            self.api_log = []
            self.max_log_size = 100

            # Search results (for frontend display)
            self.search_results = []

            # Animation
            self.current_animation = None

    def _generate_default_grid(self):
        grid_resolution = 0.1
        width = int(8.0 / grid_resolution)
        height = int(6.0 / grid_resolution)
        grid = [[0] * width for _ in range(height)]
        for i in range(width):
            grid[0][i] = 1
            grid[height - 1][i] = 1
        for j in range(height):
            grid[j][0] = 1
            grid[j][width - 1] = 1
        for name, obj in self.ROOM_OBJECTS.items():
            cx = int(obj["x"] / grid_resolution)
            cy = int(obj["y"] / grid_resolution)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        grid[ny][nx] = 1
        return grid

    def clamp_joint(self, name, angle):
        if name in self.JOINT_LIMITS:
            lo, hi = self.JOINT_LIMITS[name]
            return max(lo, min(hi, angle))
        return angle

    # ─── Joint Control ───────────────────────────────────────────

    def set_angles(self, names, angles, speed=0.2):
        """Set joint target angles — smoothly interpolated by update()."""
        with self._lock:
            if isinstance(names, str):
                names = [names]
                angles = [angles]
            if names == ["Head"] or (len(names) == 1 and names[0] == "Head"):
                names = ["HeadYaw", "HeadPitch"]
                if len(angles) == 1:
                    angles = [angles[0], angles[0]]
            for name, angle in zip(names, angles):
                if name in self._joint_targets:
                    self._joint_targets[name] = self.clamp_joint(name, angle)
                    self._joint_speeds[name] = speed

    def get_angles(self, names):
        with self._lock:
            if isinstance(names, str):
                if names == "Head":
                    return [self.joints["HeadYaw"], self.joints["HeadPitch"]]
                if names == "Body":
                    return list(self.joints.values())
                return [self.joints.get(names, 0.0)]
            return [self.joints.get(n, 0.0) for n in names]

    def set_stiffnesses(self, names, values):
        with self._lock:
            if isinstance(names, str):
                if names in ("Head", "Body", "Arms", "Legs"):
                    target_joints = {
                        "Head": ["HeadYaw", "HeadPitch"],
                        "Body": list(self.JOINT_LIMITS.keys()),
                        "Arms": [j for j in self.JOINT_LIMITS if "Shoulder" in j or "Elbow" in j or "Wrist" in j or "Hand" in j],
                        "Legs": [j for j in self.JOINT_LIMITS if "Hip" in j or "Knee" in j],
                    }.get(names, [names])
                    val = values if isinstance(values, (int, float)) else values[0]
                    for j in target_joints:
                        self.stiffnesses[j] = val
                else:
                    self.stiffnesses[names] = values if isinstance(values, (int, float)) else values[0]
            else:
                if isinstance(values, (int, float)):
                    values = [values] * len(names)
                for n, v in zip(names, values):
                    if n in self.stiffnesses:
                        self.stiffnesses[n] = v

    # ─── Movement Control ────────────────────────────────────────

    def move_to(self, x, y, theta):
        """Move to relative position — smoothly interpolated by update()."""
        with self._lock:
            # Convert relative to absolute target
            target_x = self.x + x * math.cos(self.theta) - y * math.sin(self.theta)
            target_y = self.y + x * math.sin(self.theta) + y * math.cos(self.theta)
            target_theta = self.theta + theta

            target_x = max(0.3, min(7.7, target_x))
            target_y = max(0.3, min(5.7, target_y))

            self._move_target = {
                "x": target_x,
                "y": target_y,
                "theta": target_theta
            }
            self._velocity_mode = False
            self.is_moving = True

    def move_toward(self, vx, vy, vtheta):
        """Set velocity — continuously applied by update()."""
        with self._lock:
            max_speed = self.MAX_MOVE_SPEED
            self.vx = vx * max_speed
            self.vy = vy * max_speed
            self.vtheta = vtheta * self.MAX_ROTATION_SPEED
            self._velocity_mode = True
            self._move_target = None
            self.is_moving = (vx != 0 or vy != 0 or vtheta != 0)

    def stop_move(self):
        with self._lock:
            self.vx = 0.0
            self.vy = 0.0
            self.vtheta = 0.0
            self._velocity_mode = False
            self._move_target = None
            self.is_moving = False

    def navigate_to(self, x, y, theta=0):
        """Navigate to absolute position — smoothly interpolated."""
        with self._lock:
            self._move_target = {
                "x": max(0.3, min(7.7, x)),
                "y": max(0.3, min(5.7, y)),
                "theta": theta
            }
            self.nav_target = self._move_target.copy()
            self._velocity_mode = False
            self.is_moving = True

    # ─── Posture ─────────────────────────────────────────────────

    def go_to_posture(self, posture_name, speed=0.5):
        """Change posture — joints interpolate smoothly via update()."""
        with self._lock:
            if posture_name in self.POSTURE_ANGLES:
                for joint, angle in self.POSTURE_ANGLES[posture_name].items():
                    if joint in self._joint_targets:
                        self._joint_targets[joint] = angle
                        self._joint_speeds[joint] = speed
                self.posture = posture_name
            elif posture_name in self.POSTURES:
                self.posture = posture_name
            return posture_name in self.POSTURES

    # ─── Speech ──────────────────────────────────────────────────

    def say(self, text, language=None, speed=None, pitch=None):
        with self._lock:
            self.is_speaking = True
            self.current_speech = text
            if language:
                self.speech_language = language
            if speed:
                self.speech_speed = speed
            if pitch:
                self.speech_pitch = pitch

    def stop_speaking(self):
        with self._lock:
            self.is_speaking = False
            self.current_speech = ""

    def finish_speaking(self):
        with self._lock:
            self.is_speaking = False
            self.current_speech = ""

    # ─── LEDs ────────────────────────────────────────────────────

    def set_eye_color(self, r, g, b):
        with self._lock:
            self.eye_color = {
                "r": max(0, min(255, r)),
                "g": max(0, min(255, g)),
                "b": max(0, min(255, b))
            }

    # ─── Tablet ──────────────────────────────────────────────────

    def show_tablet_url(self, url):
        with self._lock:
            self.tablet_url = url
            self.tablet_visible = True
            self.tablet_image = ""

    def show_tablet_image(self, image_url):
        with self._lock:
            self.tablet_image = image_url
            self.tablet_visible = True
            self.tablet_url = ""

    def hide_tablet(self):
        with self._lock:
            self.tablet_visible = False

    # ─── Search Results ──────────────────────────────────────────

    def push_search_result(self, query, results):
        with self._lock:
            self.search_results.append({
                "query": query,
                "results": results,
                "time": time.strftime("%H:%M:%S"),
            })
            if len(self.search_results) > 5:
                self.search_results.pop(0)

    def clear_search_results(self):
        with self._lock:
            self.search_results = []

    # ─── Queries ─────────────────────────────────────────────────

    def get_robot_position(self):
        with self._lock:
            return [self.x, self.y, self.theta]

    # ─── Physics Update ──────────────────────────────────────────

    def update(self, dt):
        """Physics tick — smoothly interpolates position and joints."""
        with self._lock:
            # ── Position interpolation ──────────────────────────
            if self._move_target is not None:
                tx = self._move_target["x"]
                ty = self._move_target["y"]
                tt = self._move_target["theta"]

                dx = tx - self.x
                dy = ty - self.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist > self.ARRIVE_THRESHOLD:
                    # Move toward target at max speed
                    step = min(self.MAX_MOVE_SPEED * dt, dist)
                    self.x += (dx / dist) * step
                    self.y += (dy / dist) * step
                    self.is_moving = True

                    # Face the direction of movement
                    move_angle = math.atan2(dy, dx)
                    angle_diff = move_angle - self.theta
                    # Normalize to [-pi, pi]
                    angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                    max_rot = self.MAX_ROTATION_SPEED * dt
                    if abs(angle_diff) > 0.05:
                        self.theta += max(-max_rot, min(max_rot, angle_diff))
                else:
                    # Arrived at position, now fix rotation
                    self.x = tx
                    self.y = ty

                    angle_diff = tt - self.theta
                    angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi

                    if abs(angle_diff) > self.ANGLE_THRESHOLD:
                        max_rot = self.MAX_ROTATION_SPEED * dt
                        self.theta += max(-max_rot, min(max_rot, angle_diff))
                        self.is_moving = True
                    else:
                        # Fully arrived
                        self.theta = tt
                        self._move_target = None
                        self.nav_target = None
                        self.is_moving = False

                # Clamp to room
                self.x = max(0.3, min(7.7, self.x))
                self.y = max(0.3, min(5.7, self.y))

            elif self._velocity_mode and self.is_moving:
                # Velocity-based movement
                self.x += (self.vx * math.cos(self.theta) - self.vy * math.sin(self.theta)) * dt
                self.y += (self.vx * math.sin(self.theta) + self.vy * math.cos(self.theta)) * dt
                self.theta += self.vtheta * dt
                self.x = max(0.3, min(7.7, self.x))
                self.y = max(0.3, min(5.7, self.y))

            # ── Joint interpolation ─────────────────────────────
            for name in self.joints:
                current = self.joints[name]
                target = self._joint_targets[name]
                if abs(current - target) > self.ANGLE_THRESHOLD:
                    speed = self._joint_speeds.get(name, 0.2)
                    # speed is fraction of max (0-1), scale to rad/s
                    max_step = self.JOINT_SPEED * speed * dt
                    diff = target - current
                    step = max(-max_step, min(max_step, diff))
                    self.joints[name] = current + step

            # ── Battery drain ───────────────────────────────────
            drain_rate = 8.0 if self.is_moving else 4.0
            self.battery -= (drain_rate / 3600.0) * dt
            self.battery = max(0.0, self.battery)

            self.last_update = time.time()

    # ─── Logging ─────────────────────────────────────────────────

    def log_api_call(self, endpoint, method, body=None, response=None):
        with self._lock:
            entry = {
                "time": time.strftime("%H:%M:%S"),
                "endpoint": endpoint,
                "method": method,
                "body": body,
                "response_preview": str(response)[:200] if response else None,
            }
            self.api_log.append(entry)
            if len(self.api_log) > self.max_log_size:
                self.api_log.pop(0)

    # ─── Serialization ───────────────────────────────────────────

    def to_dict(self):
        with self._lock:
            return {
                "position": {"x": self.x, "y": self.y, "theta": self.theta},
                "velocity": {"vx": self.vx, "vy": self.vy, "vtheta": self.vtheta},
                "is_moving": self.is_moving,
                "joints": dict(self.joints),
                "posture": self.posture,
                "battery": round(self.battery, 1),
                "charging": self.charging,
                "eye_color": self.eye_color,
                "is_speaking": self.is_speaking,
                "current_speech": self.current_speech,
                "speech_language": self.speech_language,
                "tablet": {
                    "visible": self.tablet_visible,
                    "url": self.tablet_url,
                    "image": self.tablet_image,
                },
                "autonomous_life": self.autonomous_life,
                "basic_awareness": self.basic_awareness,
                "face_tracking": self.face_tracking,
                "current_animation": self.current_animation,
                "is_exploring": self.is_exploring,
                "has_map": self.has_map,
                "nav_target": self.nav_target,
                "room_objects": self.ROOM_OBJECTS,
                "api_log": self.api_log[-20:],
                "uptime": round(time.time() - self.boot_time),
                "search_results": self.search_results,
            }
