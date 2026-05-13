import time
import queue
import threading

import cv2

from constants import *
from utils import read_config_flag
from network import ping_pi
from stream import connect_stream, release_stream
from processor import process, reset


# ── Frame queue (main thread → processor thread) ──────────────────────────────
_frame_queue = queue.Queue()


def _processor_loop():
    while True:
        frame = _frame_queue.get()
        if frame is None:   # sentinel: shut down
            break
        frame = frame[100:550, :1450]
        try:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] 'q' pressed. Shutting down...")
                break
        except Exception as e:
            print(f"[DISPLAY] Error showing frame: {e}")
        try:
            process(frame)
        except Exception as e:
            print(f"[PROCESSOR] Error: {e}")
        finally:
            _frame_queue.task_done()


_proc_thread = threading.Thread(target=_processor_loop, daemon=True, name="processor")
_proc_thread.start()


# ── Main loop (stream reading) ─────────────────────────────────────────────────
cap = None
frame_count = 0
start_time = None
last_time = None

print("[INFO] Watching config file for CAMERA_RUN flag...")

try:
    while True:
        camera_run = read_config_flag(CONFIG_FILE, "CAMERA_RUN")
        process_flag = read_config_flag(CONFIG_FILE, "PROCESS")

        if not camera_run:
            if cap is not None:
                print("[INFO] CAMERA_RUN = FALSE, disconnecting stream...")
                cap = release_stream(cap)
                reset()

            frame_count = 0
            start_time = None
            last_time = None

            print("[IDLE] Camera disabled. Waiting...")
            time.sleep(CHECK_INTERVAL)
            continue

        if not ping_pi(PI_IP):
            if cap is not None:
                print("[WARN] Pi not reachable. Stopping stream and waiting...")
                cap = release_stream(cap)
                reset()

            frame_count = 0
            start_time = None
            last_time = None

            print("[IDLE] Waiting for Pi connection...")
            time.sleep(CHECK_INTERVAL)
            continue

        if cap is None:
            print("[INFO] Pi reachable. Connecting to stream...")
            cap = connect_stream()

            if cap is None:
                print("[ERROR] Cannot open stream. Retrying...")
                time.sleep(CHECK_INTERVAL)
                continue

            print("[INFO] Stream connected.")
            frame_count = 0
            start_time = time.time()
            last_time = start_time

        ret, frame = cap.read()

        if not ret:
            print("[WARN] Frame not received. Stream lost. Waiting for Pi...")
            cap = release_stream(cap)

            frame_count = 0
            start_time = None
            last_time = None

            time.sleep(CHECK_INTERVAL)
            continue

        now = time.time()
        frame_count += 1
        last_time = now

        if process_flag:
            _frame_queue.put(frame)

except KeyboardInterrupt:
    print("\n[INFO] Interrupted by user.")

finally:
    _frame_queue.put(None)
    _proc_thread.join(timeout=2)
    if cap is not None:
        release_stream(cap)
    print("[INFO] Clean shutdown.")
