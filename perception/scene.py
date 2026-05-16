"""Scene Manager: maintains real-time scene state from vision pipeline"""

import threading
import time
from typing import Optional

from perception.vision import VisionPipeline, SceneUpdate


class SceneManager:
    """Background thread updates scene state; orchestrator reads it."""

    def __init__(self, pepper_client, vision: VisionPipeline,
                 interval: float = 1.0):
        self.pepper = pepper_client
        self.vision = vision
        self.interval = interval

        self._current_scene: Optional[SceneUpdate] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

    @property
    def current_scene(self) -> Optional[SceneUpdate]:
        with self._lock:
            return self._current_scene

    def scene_text(self) -> str:
        """Format scene as text for LLM prompt injection."""
        scene = self.current_scene
        if not scene:
            return "No scene data available."

        parts = []
        if scene.people_count > 0:
            parts.append(f"People detected: {scene.people_count}")

        if scene.faces:
            names = [f.name for f in scene.faces]
            parts.append(f"Identified: {', '.join(names)}")

        if scene.objects:
            labels = list(set(o.label for o in scene.objects if o.label != "person"))
            if labels:
                parts.append(f"Objects: {', '.join(labels)}")

        return " | ".join(parts) if parts else "Room appears empty."

    def start(self):
        self._stop.clear()
        t = threading.Thread(target=self._vision_loop, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()

    def _vision_loop(self):
        while not self._stop.is_set():
            try:
                frame_b64 = self.pepper.get_camera_frame()
                if frame_b64:
                    scene = self.vision.process_frame(frame_b64)
                    with self._lock:
                        self._current_scene = scene
            except Exception as e:
                print(f"[VISION] Error: {e}")

            time.sleep(self.interval)
