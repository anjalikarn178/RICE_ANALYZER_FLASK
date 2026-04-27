import time
import queue
import threading
import cv2

from constants import *
from utils import read_config_flag
from network import ping_pi
from stream import connect_stream, cleanup_stream
from processor import process, reset


# ── Frame queue (main thread → processor thread) ──────────────────────────────
_frame_queue = queue.Queue()


def _processor_loop():
    """Consume frames from the frame queue and run grain detection + tracking."""
    while True:
        frame = _frame_queue.get()
        if frame is None:   # sentinel: shut down
            break
        try:
            process(frame)
        except Exception as e:
            print(f"[PROCESSOR] Error: {e}")
        finally:
            _frame_queue.task_done()


_proc_thread = threading.Thread(target=_processor_loop, daemon=True, name="processor")
_proc_thread.start()


# ── Main loop (stream reading + display) ──────────────────────────────────────
cap = None
window_created = False
frame_count = 0
start_time = None
last_time = None

print("[INFO] Watching config file for CAMERA_RUN flag...")

try:
    while True:
        camera_run = read_config_flag(CONFIG_FILE, "CAMERA_RUN")
        process_flag = read_config_flag(CONFIG_FILE, "PROCESS")

        if not camera_run:
            if cap is not None or window_created:
                print("[INFO] CAMERA_RUN = FALSE, disconnecting stream...")
                cap, window_created = cleanup_stream(cap, window_created)
                reset()

            frame_count = 0
            start_time = None
            last_time = None

            print("[IDLE] Camera disabled. Waiting...")
            time.sleep(CHECK_INTERVAL)
            continue

        if not ping_pi(PI_IP):
            if cap is not None or window_created:
                print("[WARN] Pi not reachable. Stopping stream and waiting...")
                cap, window_created = cleanup_stream(cap, window_created)
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

            print("[INFO] Connected. Starting display...")
            cv2.namedWindow("Stream", cv2.WINDOW_NORMAL)
            window_created = True

            frame_count = 0
            start_time = time.time()
            last_time = start_time

        ret, frame = cap.read()

        if not ret:
            print("[WARN] Frame not received. Stream lost. Waiting for Pi...")
            cap, window_created = cleanup_stream(cap, window_created)

            frame_count = 0
            start_time = None
            last_time = None

            time.sleep(CHECK_INTERVAL)
            continue

        now = time.time()
        frame_count += 1

        delta = now - last_time
        last_time = now
        inst_fps = 1.0 / delta if delta > 0 else 0

        elapsed = now - start_time
        avg_fps = frame_count / elapsed if elapsed > 0 else 0
        drop_pct = max(0, (EXPECTED_FPS - avg_fps) / EXPECTED_FPS) * 100

        # Push frame into queue for the processor thread.
        # put_nowait drops the frame if the queue is full — display stays smooth.
        if process_flag:
            try:
                _frame_queue.put_nowait(frame)
            except queue.Full:
                pass  # processor busy; skip this frame

        cv2.imshow("Stream", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or cv2.getWindowProperty("Stream", cv2.WND_PROP_VISIBLE) < 1:
            print("[INFO] Window closed by user. Disconnecting...")
            cap, window_created = cleanup_stream(cap, window_created)
            break

except KeyboardInterrupt:
    print("\n[INFO] Interrupted by user.")

finally:
    # Send sentinel to stop the processor thread cleanly
    _frame_queue.put(None)
    _proc_thread.join(timeout=2)
    cap, window_created = cleanup_stream(cap, window_created)
    print("[INFO] Clean shutdown.")
