"""Phase 8: Health Monitor — structured logging + metrics."""

import time
import json
import os
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime


class HealthMonitor:
    """Collects metrics and writes structured JSON logs."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self._metrics: Dict[str, list] = {
            "llm_latency": [],
            "vision_latency": [],
            "stt_latency": [],
        }
        self._log_file = self._open_log()

    def _open_log(self):
        date = datetime.now().strftime("%Y-%m-%d")
        path = self.log_dir / f"pepper_{date}.jsonl"
        return open(path, "a", encoding="utf-8")

    def log_event(self, event_type: str, data: Dict):
        """Write a structured JSON log line."""
        entry = {
            "ts": datetime.now().isoformat(),
            "type": event_type,
            **data,
        }
        self._log_file.write(json.dumps(entry) + "\n")
        self._log_file.flush()

    def log_llm_call(self, brain: str, tokens: int, latency: float,
                     tok_per_sec: float, success: bool):
        self.log_event("llm_call", {
            "brain": brain,
            "tokens": tokens,
            "latency_s": round(latency, 2),
            "tok_per_sec": round(tok_per_sec, 1),
            "success": success,
        })
        self._metrics["llm_latency"].append(latency)

    def log_interaction(self, user_text: str, response_text: str,
                        route: str, person_id: Optional[str] = None):
        self.log_event("interaction", {
            "user": user_text[:200],
            "response": response_text[:200],
            "route": route,
            "person": person_id,
        })

    def log_error(self, component: str, error: str):
        self.log_event("error", {"component": component, "error": error})

    def write_heartbeat(self, heartbeat_path: str = "/tmp/pepper_heartbeat"):
        """Write heartbeat file for watchdog."""
        Path(heartbeat_path).write_text(str(time.time()))

    def get_p95_latency(self, metric: str = "llm_latency") -> float:
        values = self._metrics.get(metric, [])
        if not values:
            return 0.0
        values_sorted = sorted(values)
        idx = int(len(values_sorted) * 0.95)
        return values_sorted[min(idx, len(values_sorted) - 1)]

    def close(self):
        self._log_file.close()
