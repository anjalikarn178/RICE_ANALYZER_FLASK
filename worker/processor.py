"""
Frame processor: grain detection → gated velocity tracker → AI classification queue.

Called once per frame from main.py. All state (tracker, background modeler, classifier) is
module-level so it persists across frames.
"""

import cv2
import numpy as np

from grain_counter import detect_grains, GatedVelocityTracker, BackgroundCalibrator, SpikeGuard
from classifier import AIClassifier
import data_io

RICE_MODE = "auto"   # "auto" uses belt-background subtraction or dynamic auto-calibrated background

# GatedVelocityTracker parameters from mask+tracking.py
_tracker = GatedVelocityTracker(max_missed=3, gate_radius=70.0, estimated_speed=145.0)
_bg_calibrator = BackgroundCalibrator(background_frames_needed=30, sample_every=5, threshold_margin=5)
_spike_guard = SpikeGuard()
_classifier = AIClassifier()

# Default counting zone lines (from mask+tracking.py)
TOP_LINE_Y = 70
BOTTOM_LINE_Y = 650


def process(frame: np.ndarray):
    """
    Process one stream frame:
    1. Accumulate calibration frames if background model isn't ready.
    2. Detect grain contours using background subtraction / HSV mask and ROI counting zone.
    3. Compute centroid per valid contour.
    4. Spike-guard: skip frames with anomalous detection counts.
    5. Update gated velocity tracker — get indices of newly seen grains.
    6. Increment total count and enqueue new grain crops for AI classification.
    """
    # Build background model dynamically if not yet calibrated
    if not _bg_calibrator.is_calibrated:
        _bg_calibrator.add_frame(frame)

    h, w = frame.shape[:2]
    top_y = min(TOP_LINE_Y, int(h * 0.1)) if h <= TOP_LINE_Y else TOP_LINE_Y
    bottom_y = min(BOTTOM_LINE_Y, int(h * 0.9)) if h <= BOTTOM_LINE_Y else BOTTOM_LINE_Y

    contours, _ = detect_grains(
        frame,
        mode=RICE_MODE,
        top_line_y=top_y,
        bottom_line_y=bottom_y,
        bg_calibrator=_bg_calibrator,
    )

    # Build parallel lists: centroid, contour, area — all same length.
    centroids = []
    valid_contours = []
    valid_areas = []
    for c in contours:
        M = cv2.moments(c)
        if M["m00"] > 0:
            centroids.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))
            valid_contours.append(c)
            valid_areas.append(cv2.contourArea(c))

    if _spike_guard.is_spike(len(centroids)):
        return

    _, new_indices = _tracker.update(centroids, valid_areas)

    if not new_indices:
        return

    # Update total count in data.json
    data_io.update_total(len(new_indices))

    # Extract crop for each new grain and queue for AI classification
    for di in new_indices:
        if di >= len(valid_contours):
            continue
        cnt = valid_contours[di]
        area = valid_areas[di]

        x, y, bw, bh = cv2.boundingRect(cnt)
        pad = 5
        x1 = max(x - pad, 0)
        y1 = max(y - pad, 0)
        x2 = min(x + bw + pad, w)
        y2 = min(y + bh + pad, h)

        crop = frame[y1:y2, x1:x2]
        if crop.size > 0:
            _classifier.enqueue(crop, area)


def reset():
    """Reset tracker, background calibrator, spike guard, and data file. Call when user starts a new batch."""
    _tracker.reset()
    _bg_calibrator.reset()
    _spike_guard.reset()
    data_io.reset()
