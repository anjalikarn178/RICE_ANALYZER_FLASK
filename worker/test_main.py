"""
Video-file worker — temporary testing counterpart to main.py.

Instead of pulling frames from the Pi stream, this watches test.json (written by the
/test page in the interface) and runs an uploaded video file through the exact same
processor: detection → gated velocity tracker → AI classification → data.json.

Run it the same way as main.py:
    python test_main.py

Control file  (test.json, written by the UI):
    {"RUN": bool, "VIDEO_PATH": "test_videos/clip.mp4", "REALTIME": bool, "RUN_ID": str}
Status file   (test_status.json, written here, polled by the UI):
    {"state": "idle|running|done|stopped|error", "run_id": str, "updated_at": float, ...}

`updated_at` is refreshed roughly twice a second even while idle, so the UI can tell a
live worker from a status file left behind by a dead one. `run_id` is echoed back from
the control file so the UI only ever trusts status from the run it actually started.
"""

import os
import sys
import json
import time

# Allow `python test_main.py` from any cwd — worker modules use flat imports.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2

from constants import (
    PARENT_DIR,
    CHECK_INTERVAL,
    TEST_CONTROL_FILE,
    TEST_STATUS_FILE,
    TEST_PREVIEW_FILE,
    TEST_VIDEO_DIR,
)
from processor import process, reset, _tracker, _bg_calibrator, TOP_LINE_Y, BOTTOM_LINE_Y

PREVIEW_EVERY = 5      # frames between preview/status writes
CONTROL_EVERY = 5      # frames between control-file re-reads (so Stop is responsive)


# ── Control / status files ────────────────────────────────────────────────────
def read_control() -> dict:
    try:
        with open(TEST_CONTROL_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return {}


def _write_atomic(path: str, write_fn):
    """Write via a temp file + rename so the UI never reads a half-written file.
    The temp name keeps the real extension — cv2.imwrite picks its encoder from it —
    and carries the pid, so a second worker can't clobber this one's temp file."""
    stem, ext = os.path.splitext(path)
    tmp = f"{stem}.tmp{os.getpid()}{ext}"
    try:
        write_fn(tmp)
        os.replace(tmp, path)
    except Exception as e:
        print(f"[TEST] Write failed for {path}: {e}")


# Last status payload, so the heartbeat can refresh its timestamp without
# losing the state/message it reports.
_last_status: dict = {}


def _flush_status():
    def _write(tmp):
        with open(tmp, "w") as f:
            json.dump(_last_status, f, indent=4)

    _write_atomic(TEST_STATUS_FILE, _write)


def write_status(state: str, video: str = "", frame: int = 0,
                 total_frames: int = 0, message: str = "", run_id: str = ""):
    _last_status.update({
        "state": state,
        "video": video,
        "frame": frame,
        "total_frames": total_frames,
        "message": message,
        "run_id": run_id,
        "updated_at": time.time(),
    })
    _flush_status()


def touch_status():
    """Heartbeat: refresh updated_at only, so the UI can tell a live worker from a
    dead one. Without this a stale status file looks exactly like an idle worker."""
    if not _last_status:
        return
    _last_status["updated_at"] = time.time()
    _flush_status()


def write_preview(frame):
    def _write(tmp):
        cv2.imwrite(tmp, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])

    _write_atomic(TEST_PREVIEW_FILE, _write)


def resolve_video_path(raw: str) -> str:
    """Accept an absolute path, or one relative to the project root / test_videos."""
    if not raw:
        return ""
    if os.path.isabs(raw):
        return raw
    candidate = os.path.abspath(os.path.join(PARENT_DIR, raw))
    if os.path.exists(candidate):
        return candidate
    return os.path.abspath(os.path.join(TEST_VIDEO_DIR, os.path.basename(raw)))


# ── Preview overlay (same annotations as the old cv2.imshow test runner) ──────
def annotate(frame, top_y: int, bottom_y: int):
    vis = frame.copy()
    h, w = vis.shape[:2]

    cv2.line(vis, (0, top_y), (w - 1, top_y), (0, 0, 255), 2)
    cv2.line(vis, (0, bottom_y), (w - 1, bottom_y), (0, 0, 255), 2)

    for object_id, (cx, cy) in _tracker.objects.items():
        cv2.circle(vis, (cx, cy), 4, (0, 0, 255), -1)
        cv2.putText(vis, f"ID {object_id}", (cx - 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

        if object_id in _tracker.predictions:
            px, py, radius = _tracker.predictions[object_id]
            cv2.circle(vis, (px, py), int(radius), (0, 165, 255), 1, cv2.LINE_AA)
            cv2.line(vis, (cx, cy), (px, py), (255, 0, 255), 1, cv2.LINE_AA)

    bg_status = (
        "READY" if _bg_calibrator.is_calibrated
        else f"CALIBRATING ({len(_bg_calibrator.background_frames)}/{_bg_calibrator.background_frames_needed})"
    )
    cv2.putText(vis, f"Total Grains Tracked: {_tracker._nid}", (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(vis, f"BG Model: {bg_status}", (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1, cv2.LINE_AA)
    return vis


# ── One video run ─────────────────────────────────────────────────────────────
def run_video(video_path: str, realtime: bool, run_id: str = "") -> str:
    """Process a whole video file. Returns the terminal state: done / stopped / error."""
    name = os.path.basename(video_path)

    if not os.path.exists(video_path):
        write_status("error", name, message=f"File not found: {video_path}", run_id=run_id)
        print(f"[TEST] File not found: {video_path}")
        return "error"

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        write_status("error", name, message=f"Unable to open video: {name}", run_id=run_id)
        print(f"[TEST] Unable to open video: {video_path}")
        return "error"

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_delay = (1.0 / fps) if (realtime and fps > 0) else 0.0

    top_y = min(TOP_LINE_Y, int(height * 0.1)) if height <= TOP_LINE_Y else TOP_LINE_Y
    bottom_y = min(BOTTOM_LINE_Y, int(height * 0.9)) if height <= BOTTOM_LINE_Y else BOTTOM_LINE_Y

    print(f"[TEST] Processing {name} — {width}x{height} @ {fps:.2f} fps, "
          f"{total_frames if total_frames > 0 else 'unknown'} frames")

    # Fresh tracker/background/counts for every run.
    reset()

    frame_number = 0
    state = "done"
    started = time.time()
    write_status("running", name, 0, max(total_frames, 0), run_id=run_id)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_number += 1
        try:
            process(frame)
        except Exception as e:
            print(f"[TEST] Processor error on frame {frame_number}: {e}")

        if frame_number % PREVIEW_EVERY == 0:
            write_preview(annotate(frame, top_y, bottom_y))
            write_status("running", name, frame_number, max(total_frames, 0), run_id=run_id)

        if frame_number % CONTROL_EVERY == 0 and not read_control().get("RUN", False):
            print("[TEST] RUN = false — stopping early.")
            state = "stopped"
            break

        if frame_delay:
            time.sleep(frame_delay)

    cap.release()

    elapsed = time.time() - started
    message = (f"{frame_number} frames in {elapsed:.1f}s — "
               f"{_tracker._nid} unique grains tracked")
    write_status(state, name, frame_number, max(total_frames, 0), message, run_id=run_id)
    print(f"[TEST] {state.upper()}: {message}")
    return state


# ── Watch loop ────────────────────────────────────────────────────────────────
def main():
    print(f"[TEST] Watching {TEST_CONTROL_FILE} for RUN flag...")
    write_status("idle")
    last_finished = None   # run key already processed for the current RUN=true

    try:
        while True:
            control = read_control()
            run_flag = bool(control.get("RUN", False))
            video_path = resolve_video_path(str(control.get("VIDEO_PATH", "")).strip())
            run_id = str(control.get("RUN_ID", "")).strip()

            # A run is identified by RUN_ID when the UI supplies one, so pressing Start
            # twice on the same clip is two runs. Falls back to the path for a
            # hand-edited test.json.
            run_key = run_id or video_path

            if not run_flag:
                last_finished = None
                touch_status()
                time.sleep(CHECK_INTERVAL)
                continue

            if not video_path:
                write_status("error", message="No video selected.", run_id=run_id)
                time.sleep(CHECK_INTERVAL)
                continue

            # Already handled this run; heartbeat and wait for stop/next Start.
            if run_key == last_finished:
                touch_status()
                time.sleep(CHECK_INTERVAL)
                continue

            run_video(video_path, bool(control.get("REALTIME", False)), run_id)
            last_finished = run_key

    except KeyboardInterrupt:
        print("\n[TEST] Interrupted by user.")
    finally:
        write_status("idle")
        print("[TEST] Clean shutdown.")


if __name__ == "__main__":
    main()
