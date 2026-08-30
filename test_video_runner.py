"""
Test Runner for Rice Grain Detection & Tracking using a Video File.

Usage:
    python test_video_runner.py [optional_path_to_video.mp4]
"""

import os
import sys
import time
import json
import cv2
import numpy as np

# Ensure worker directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_DIR = os.path.join(BASE_DIR, "worker")
if WORKER_DIR not in sys.path:
    sys.path.insert(0, WORKER_DIR)

from worker.processor import process, reset, _tracker, _bg_calibrator, TOP_LINE_Y, BOTTOM_LINE_Y
import worker.data_io

# Default test video path (update this if your video file is located elsewhere)
DEFAULT_VIDEO_PATH = r"/Users/udit/Downloads/vid_samples-6thAug 2/1785995939.9004526-black.mp4"


def main():
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = DEFAULT_VIDEO_PATH

    print("==================================================")
    print(" Rice Analyzer - Video Test Runner ")
    print("==================================================")
    print(f"Target Video Path: {video_path}")

    if not os.path.exists(video_path):
        print(f"\n[ERROR] Video file not found at: {video_path}")
        print("Please provide a valid video file path as a command-line argument:")
        print("  python test_video_runner.py <path_to_video.mp4>\n")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"\n[ERROR] Unable to open video source: {video_path}")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"Resolution : {frame_width} x {frame_height}")
    print(f"FPS        : {fps:.2f}")
    print(f"Total Frames: {total_frames if total_frames > 0 else 'Unknown'}")
    print("--------------------------------------------------")

    # Reset worker tracker and data file before starting batch
    reset()

    frame_number = 0
    start_time = time.time()

    print("[INFO] Processing frames... Press 'q' or 'ESC' on the preview window to exit.\n")

    top_y = min(TOP_LINE_Y, int(frame_height * 0.1)) if frame_height <= TOP_LINE_Y else TOP_LINE_Y
    bottom_y = min(BOTTOM_LINE_Y, int(frame_height * 0.9)) if frame_height <= BOTTOM_LINE_Y else BOTTOM_LINE_Y

    while True:
        ret, frame = cap.read()
        if not ret:
            print("\n[INFO] End of video reached.")
            break

        frame_number += 1
        process(frame)

        # Build visual output overlay for live preview
        vis_frame = frame.copy()

        # Draw counting zone lines
        cv2.line(vis_frame, (0, top_y), (frame_width - 1, top_y), (0, 0, 255), 2)
        cv2.line(vis_frame, (0, bottom_y), (frame_width - 1, bottom_y), (0, 0, 255), 2)
        cv2.putText(vis_frame, f"TOP: {top_y}", (10, max(top_y - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(vis_frame, f"BOTTOM: {bottom_y}", (10, max(bottom_y - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)

        # Draw tracked objects, predictions, and trajectories
        for objectID, (curr_x, curr_y) in _tracker.objects.items():
            cv2.circle(vis_frame, (curr_x, curr_y), 4, (0, 0, 255), -1)
            cv2.putText(vis_frame, f"ID {objectID}", (curr_x - 10, curr_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

            if objectID in _tracker.predictions:
                pred_x, pred_y, radius = _tracker.predictions[objectID]
                # Draw safety net sphere
                cv2.circle(vis_frame, (pred_x, pred_y), int(radius), (0, 165, 255), 1, cv2.LINE_AA)
                # Draw trajectory line
                cv2.line(vis_frame, (curr_x, curr_y), (pred_x, pred_y), (255, 0, 255), 1, cv2.LINE_AA)

        # Draw total grain count overlay
        bg_status = "READY" if _bg_calibrator.is_calibrated else f"CALIBRATING ({len(_bg_calibrator.background_frames)}/30)"
        cv2.putText(vis_frame, f"Total Grains Tracked: {_tracker._nid}", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis_frame, f"BG Model: {bg_status}", (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 1, cv2.LINE_AA)

        # Display window
        cv2.imshow("Rice Analyzer - Video Test", vis_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):
            print("\n[INFO] Stopped by user.")
            break

    cap.release()
    cv2.destroyAllWindows()

    elapsed = time.time() - start_time
    print("==================================================")
    print(" TEST COMPLETED ")
    print("==================================================")
    print(f"Total Frames Processed : {frame_number}")
    print(f"Time Elapsed           : {elapsed:.2f} seconds")
    print(f"Total Unique Grains    : {_tracker._nid}")

    # Read data.json to display classification summary
    data_file = os.path.join(BASE_DIR, "data.json")
    if os.path.exists(data_file):
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
            print("\ndata.json Summary:")
            print(json.dumps(data, indent=4))
        except Exception as e:
            print(f"[WARN] Could not read data.json: {e}")

    print("==================================================")


if __name__ == "__main__":
    main()
