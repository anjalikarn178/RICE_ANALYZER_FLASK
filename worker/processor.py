"""
Frame processor: grain detection → tracker → AI classification queue.

Called once per frame from main.py.  All state (tracker, classifier) is
module-level so it persists across frames.
"""

import cv2
import numpy as np

from grain_counter import detect_grains, UniqueGrainTracker, SpikeGuard
from classifier import AIClassifier
import data_io

RICE_MODE = "auto"   # "auto" uses belt-background subtraction — works for all rice types

_tracker    = UniqueGrainTracker(max_dist=45, max_missed=3)
_spike_guard = SpikeGuard()
_classifier  = AIClassifier()


def process(frame: np.ndarray):
    """
    Process one frame:
    1. Detect grain contours (background subtraction + morphology).
    2. Compute one centroid per contour.
    3. Spike-guard: skip frames with anomalous detection counts.
    4. Update tracker — get indices of newly seen grains.
    5. Increment total count and enqueue new grain crops for AI classification.
    """
    contours, _ = detect_grains(frame, RICE_MODE)

    # Build parallel lists: centroid, contour, area — all same length.
    centroids      = []
    valid_contours = []
    valid_areas    = []
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
    h, w = frame.shape[:2]
    for di in new_indices:
        cnt  = valid_contours[di]
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
    """Reset tracker, spike guard, and data file. Call when user starts a new batch."""
    _tracker.reset()
    _spike_guard.reset()
    data_io.reset()
