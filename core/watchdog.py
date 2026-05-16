#!/usr/bin/env python3
"""Phase 8: Watchdog — separate process that restarts main if it hangs.

Run as: python core/watchdog.py
Monitors /tmp/pepper_heartbeat — if stale > 30s, restarts main.py.
"""

import time
import subprocess
import sys
from pathlib import Path

HEARTBEAT_PATH = "/tmp/pepper_heartbeat"
STALE_THRESHOLD = 30  # seconds
CHECK_INTERVAL = 10
MAIN_SCRIPT = "main.py"


def read_heartbeat() -> float:
    path = Path(HEARTBEAT_PATH)
    if not path.exists():
        return 0
    try:
        return float(path.read_text().strip())
    except (ValueError, OSError):
        return 0


def is_stale() -> bool:
    last_beat = read_heartbeat()
    if last_beat == 0:
        return True
    return (time.time() - last_beat) > STALE_THRESHOLD


def main():
    print(f"[WATCHDOG] Monitoring heartbeat at {HEARTBEAT_PATH}")
    print(f"[WATCHDOG] Stale threshold: {STALE_THRESHOLD}s")

    process = None
    consecutive_stale = 0

    while True:
        if is_stale():
            consecutive_stale += 1
            print(f"[WATCHDOG] Heartbeat stale ({consecutive_stale}x)")

            if consecutive_stale >= 3:
                print("[WATCHDOG] Restarting main process...")
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)

                process = subprocess.Popen(
                    [sys.executable, MAIN_SCRIPT],
                    cwd=str(Path(__file__).parent.parent)
                )
                consecutive_stale = 0
                print(f"[WATCHDOG] Main restarted (PID: {process.pid})")
        else:
            consecutive_stale = 0

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
