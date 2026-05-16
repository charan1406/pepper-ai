"""Vision: YOLO26n object detection + InsightFace identification (dlib fallback)"""

import base64
import time
import numpy as np
import cv2
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from pathlib import Path

import config


@dataclass
class DetectedObject:
    label: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)


@dataclass
class DetectedFace:
    name: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)
    encoding: Optional[np.ndarray] = field(default=None, repr=False)


@dataclass
class SceneUpdate:
    objects: List[DetectedObject] = field(default_factory=list)
    faces: List[DetectedFace] = field(default_factory=list)
    people_count: int = 0
    timestamp: float = 0


class VisionPipeline:
    def __init__(self,
                 yolo_model: str = config.YOLO_MODEL,
                 yolo_confidence: float = config.YOLO_CONFIDENCE,
                 face_tolerance: float = config.FACE_RECOGNITION_TOLERANCE,
                 face_model: str = config.FACE_RECOGNITION_MODEL,
                 encodings_dir: str = "pepper_brain/encodings"):
        from ultralytics import YOLO
        self.yolo = YOLO(yolo_model)
        self.yolo.to("cpu")
        self.yolo_confidence = yolo_confidence

        self.face_tolerance = face_tolerance
        self.face_model = face_model
        self._face_backend = None  # "insightface" or "dlib"
        self._face_app = None

        self.known_encodings: Dict[str, np.ndarray] = {}
        self.encodings_dir = Path(encodings_dir)

        self._init_face_backend()
        self._load_known_faces()

    def _init_face_backend(self):
        """Try InsightFace first, fall back to dlib face_recognition."""
        if config.FACE_RECOGNITION_BACKEND == "insightface":
            try:
                import insightface
                self._face_app = insightface.app.FaceAnalysis(
                    name=self.face_model,
                    providers=['CPUExecutionProvider']
                )
                self._face_app.prepare(ctx_id=-1, det_size=(320, 320))
                self._face_backend = "insightface"
                return
            except (ImportError, Exception):
                pass

        try:
            import face_recognition as fr
            self._face_app = fr
            self._face_backend = "dlib"
        except (ImportError, RuntimeError):
            self._face_backend = None

    def _load_known_faces(self):
        if not self.encodings_dir.exists():
            return
        for npy_file in self.encodings_dir.glob("*.npy"):
            name = npy_file.stem
            self.known_encodings[name] = np.load(npy_file)

    def _decode_frame(self, b64_jpeg: str) -> np.ndarray:
        jpeg_bytes = base64.b64decode(b64_jpeg)
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def detect_objects(self, frame: np.ndarray) -> List[DetectedObject]:
        results = self.yolo(frame, conf=self.yolo_confidence, verbose=False)
        objects = []
        for r in results:
            for box in r.boxes:
                label = self.yolo.names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                objects.append(DetectedObject(label, conf, (x1, y1, x2, y2)))
        return objects

    def detect_faces(self, frame: np.ndarray) -> List[DetectedFace]:
        if self._face_backend == "insightface":
            return self._detect_faces_insightface(frame)
        elif self._face_backend == "dlib":
            return self._detect_faces_dlib(frame)
        return []

    def _detect_faces_insightface(self, frame: np.ndarray) -> List[DetectedFace]:
        faces_detected = self._face_app.get(frame)
        faces = []
        for face in faces_detected:
            encoding = face.embedding
            name = "unknown"
            best_sim = 0.0

            for known_name, known_enc in self.known_encodings.items():
                sim = np.dot(encoding, known_enc) / (
                    np.linalg.norm(encoding) * np.linalg.norm(known_enc)
                )
                if sim > best_sim and sim > self.face_tolerance:
                    best_sim = sim
                    name = known_name

            x1, y1, x2, y2 = face.bbox.astype(int).tolist()
            faces.append(DetectedFace(
                name=name,
                confidence=best_sim if name != "unknown" else 0.0,
                bbox=(x1, y1, x2, y2),
                encoding=encoding
            ))
        return faces

    def _detect_faces_dlib(self, frame: np.ndarray) -> List[DetectedFace]:
        fr = self._face_app
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = fr.face_locations(rgb, model="hog")
        encodings = fr.face_encodings(rgb, locations)

        faces = []
        for (top, right, bottom, left), encoding in zip(locations, encodings):
            name = "unknown"
            best_distance = 1.0

            for known_name, known_enc in self.known_encodings.items():
                distance = fr.face_distance([known_enc], encoding)[0]
                if distance < best_distance and distance < 0.6:
                    best_distance = distance
                    name = known_name

            faces.append(DetectedFace(
                name=name,
                confidence=1.0 - best_distance,
                bbox=(left, top, right, bottom),
                encoding=encoding
            ))
        return faces

    def process_frame(self, b64_jpeg: str) -> SceneUpdate:
        frame = self._decode_frame(b64_jpeg)

        objects = self.detect_objects(frame)
        faces = self.detect_faces(frame)
        people_count = sum(1 for o in objects if o.label == "person")

        return SceneUpdate(
            objects=objects,
            faces=faces,
            people_count=people_count,
            timestamp=time.time()
        )

    def enroll_face(self, name: str, b64_frames: List[str]) -> bool:
        """Enroll a new person from multiple camera frames."""
        if self._face_backend is None:
            return False

        all_encodings = []
        for b64 in b64_frames:
            frame = self._decode_frame(b64)
            if self._face_backend == "insightface":
                faces = self._face_app.get(frame)
                if faces:
                    all_encodings.append(faces[0].embedding)
            else:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                encodings = self._face_app.face_encodings(rgb)
                if encodings:
                    all_encodings.append(encodings[0])

        if not all_encodings:
            return False

        avg_encoding = np.mean(all_encodings, axis=0)
        self.encodings_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.encodings_dir / f"{name}.npy", avg_encoding)
        self.known_encodings[name] = avg_encoding
        return True
