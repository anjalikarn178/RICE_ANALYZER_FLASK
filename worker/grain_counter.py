"""
Grain detection and unique-ID tracking for real-time rice analysis.
Includes GatedVelocityTracker (velocity prediction + probability safety net gating + Hungarian matching),
Stream background calibration model, and counting zone ROI filtering.
"""

import cv2
import numpy as np
import math
from collections import deque
from typing import List, Optional, Tuple, Dict

try:
    from scipy.optimize import linear_sum_assignment
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


BROKEN_AREA_THRESHOLD = 300  # px² — grains below this are broken


class BackgroundCalibrator:
    """
    Stream-friendly dynamic background modeler & auto-calibrator.
    Accumulates initial frames to compute median background and percentile threshold (DIFF_THRESHOLD).
    """

    def __init__(self, background_frames_needed: int = 30, sample_every: int = 5, threshold_margin: int = 5):
        self.background_frames_needed = background_frames_needed
        self.sample_every = sample_every
        self.threshold_margin = threshold_margin

        self.background_frames: list = []
        self.background: Optional[np.ndarray] = None
        self.diff_threshold: int = 15
        self.is_calibrated: bool = False

    def add_frame(self, frame: np.ndarray) -> bool:
        """Add frame to calibration stack. Returns True when calibration completes."""
        if self.is_calibrated:
            return True

        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        self.background_frames.append(blurred)

        if len(self.background_frames) >= self.background_frames_needed:
            self._calibrate()
            return True
        return False

    def _calibrate(self):
        """Compute median background and 99.99th percentile diff threshold."""
        stack = np.stack(self.background_frames, axis=0)
        self.background = np.median(stack, axis=0).astype(np.uint8)

        calibration_samples = stack[:: self.sample_every]
        background_float = self.background.astype(np.float32)
        samples_float = calibration_samples.astype(np.float32)
        differences = np.abs(samples_float - background_float)
        all_diff = differences.ravel()

        p9999 = np.percentile(all_diff, 99.99)
        self.diff_threshold = max(math.ceil(p9999) + self.threshold_margin, 3)
        self.is_calibrated = True

        # Clear buffer to save memory
        self.background_frames.clear()
        print(f"[BG_MODEL] Calibration ready. Automatic DIFF_THRESHOLD = {self.diff_threshold}")

    def get_mask(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Generate binary mask via background subtraction using calibrated threshold."""
        if not self.is_calibrated or self.background is None:
            return None

        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        diff = cv2.absdiff(blurred, self.background)
        diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        _, mask = cv2.threshold(diff_gray, self.diff_threshold, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

    def reset(self):
        self.background_frames.clear()
        self.background = None
        self.diff_threshold = 15
        self.is_calibrated = False


def _make_mask(frame: np.ndarray, mode: str = "auto") -> np.ndarray:
    """Build a binary mask isolating grain pixels via belt-background subtraction (HSV fallback)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    if mode in ("auto", "mixed", "universal"):
        bg_belt   = cv2.inRange(hsv, (85, 40, 30),  (145, 255, 255))
        bg_shadow = cv2.inRange(hsv, (85, 30, 5),   (145, 255, 80))
        bg        = cv2.bitwise_or(bg_belt, bg_shadow)
        fg        = cv2.bitwise_not(bg)
        valid_v   = cv2.inRange(hsv, (0, 0, 20),    (180, 255, 255))
        m = cv2.bitwise_and(fg, valid_v)
    elif mode == "dark":
        m = cv2.inRange(hsv, (0, 0, 10), (180, 255, 75))
    elif mode == "brown":
        m = cv2.inRange(hsv, (5, 20, 60), (30, 210, 210))
    else:  # white / chalky
        m  = cv2.inRange(hsv, (0, 0, 100), (180, 90, 255))
        m |= cv2.inRange(hsv, (0, 0, 75),  (180, 55, 200))
        belt = cv2.inRange(hsv, (90, 70, 40), (135, 255, 255))
        m = cv2.bitwise_and(m, cv2.bitwise_not(belt))

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,  k3, iterations=1)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k5, iterations=2)
    return m


def detect_grains(
    frame: np.ndarray,
    mode: str = "auto",
    min_area: int = 40,
    max_area: int = 5000,
    border_margin: int = 2,
    top_line_y: Optional[int] = None,
    bottom_line_y: Optional[int] = None,
    bg_calibrator: Optional[BackgroundCalibrator] = None,
) -> Tuple[list, np.ndarray]:
    """
    Detect grain contours in frame.
    Returns (valid_contours, binary_mask).
    Filters: area range, border-touching blobs, and ROI counting zone lines.
    """
    mask = None
    if bg_calibrator is not None and bg_calibrator.is_calibrated:
        mask = bg_calibrator.get_mask(frame)

    if mask is None:
        mask = _make_mask(frame, mode)

    h_f, w_f = frame.shape[:2]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = []
    for c in contours:
        area = cv2.contourArea(c)
        if area <= min_area or area >= max_area:
            continue

        x, y, w, h = cv2.boundingRect(c)
        if border_margin > 0 and (
            x <= border_margin or y <= border_margin or
            x + w >= w_f - border_margin or y + h >= h_f - border_margin
        ):
            continue

        # Counting Zone ROI Filter (from mask+tracking.py)
        if top_line_y is not None or bottom_line_y is not None:
            grain_top = y
            grain_bottom = y + h
            if top_line_y is not None and grain_bottom < top_line_y:
                continue
            if bottom_line_y is not None and grain_top > bottom_line_y:
                continue

        valid.append(c)
    return valid, mask


class GatedVelocityTracker:
    """
    Gated Velocity Tracker from mask+tracking.py:
    Predicts position using smoothed velocity vectors, applies a probability safety net
    (gating filter radius), and matches using global Hungarian assignment.
    """

    def __init__(self, max_missed: int = 3, gate_radius: float = 70.0, estimated_speed: float = 145.0):
        self.max_missed = max_missed
        self.gate_radius = gate_radius
        self.estimated_speed = estimated_speed

        self._nid: int = 0
        self.objects: Dict[int, Tuple[int, int]] = {}
        self.velocities: Dict[int, Tuple[int, int]] = {}
        self.predictions: Dict[int, Tuple[int, int, float]] = {}
        self.disappeared: Dict[int, int] = {}
        self._grain_areas: Dict[int, float] = {}

    def register(self, centroid: Tuple[int, int], area: float = 0.0) -> int:
        assigned_id = self._nid
        self.objects[assigned_id] = centroid
        self.velocities[assigned_id] = (0, int(self.estimated_speed))
        self.disappeared[assigned_id] = 0
        self._grain_areas[assigned_id] = area
        self._nid += 1
        return assigned_id

    def deregister(self, objectID: int):
        if objectID in self.objects:
            del self.objects[objectID]
        if objectID in self.velocities:
            del self.velocities[objectID]
        if objectID in self.disappeared:
            del self.disappeared[objectID]
        if objectID in self.predictions:
            del self.predictions[objectID]

    def update(self, centroids: list, areas: Optional[list] = None) -> Tuple[int, list]:
        """
        Update tracker with frame detections.

        Returns:
            (total_unique_count, new_detection_indices)
        """
        if len(centroids) == 0:
            for oid in list(self.disappeared.keys()):
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_missed:
                    self.deregister(oid)
            return self._nid, []

        input_centroids = np.array(centroids, dtype=np.int32)
        new_det_indices = []

        if len(self.objects) == 0:
            for i, c in enumerate(centroids):
                a = areas[i] if areas and i < len(areas) else 0.0
                self.register(c, a)
                new_det_indices.append(i)
        else:
            objectIDs = list(self.objects.keys())
            predicted_centroids = []
            self.predictions.clear()

            for oid in objectIDs:
                cx, cy = self.objects[oid]
                vx, vy = self.velocities[oid]
                pred_x = int(cx + vx)
                pred_y = int(cy + vy)
                predicted_centroids.append((pred_x, pred_y))
                self.predictions[oid] = (pred_x, pred_y, self.gate_radius)

            predicted_centroids = np.array(predicted_centroids, dtype=np.float64)

            # Euclidean distance between PREDICTED centroids and NEW detections
            D = np.linalg.norm(predicted_centroids[:, np.newaxis] - input_centroids, axis=2)

            # Apply Probability Safety Net (Gating Filter)
            for r in range(len(objectIDs)):
                for c in range(len(input_centroids)):
                    if D[r, c] > self.gate_radius:
                        D[r, c] = 1e6  # Infinite penalty

            # Global Hungarian Matching
            if _HAS_SCIPY:
                rows, cols = linear_sum_assignment(D)
            else:
                rows, cols = self._greedy_match(D)

            used_rows, used_cols = set(), set()

            for row, col in zip(rows, cols):
                if row in used_rows or col in used_cols:
                    continue

                if D[row, col] >= 1e5:  # Rejected gating threshold
                    continue

                oid = objectIDs[row]
                new_c = tuple(input_centroids[col])
                old_c = self.objects[oid]

                # Exponential smoothing of velocity vectors
                new_vx = new_c[0] - old_c[0]
                new_vy = new_c[1] - old_c[1]

                prev_vx, prev_vy = self.velocities[oid]
                smoothed_vx = int(0.3 * prev_vx + 0.7 * new_vx)
                smoothed_vy = int(0.3 * prev_vy + 0.7 * new_vy)

                self.objects[oid] = new_c
                self.velocities[oid] = (smoothed_vx, smoothed_vy)
                self.disappeared[oid] = 0
                if areas and col < len(areas):
                    self._grain_areas[oid] = max(self._grain_areas.get(oid, 0.0), areas[col])

                used_rows.add(row)
                used_cols.add(col)

            # Unmatched existing IDs
            unused_rows = set(range(0, D.shape[0])).difference(used_rows)
            for row in unused_rows:
                oid = objectIDs[row]
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_missed:
                    self.deregister(oid)

            # Unmatched new detections
            unused_cols = set(range(0, D.shape[1])).difference(used_cols)
            for col in unused_cols:
                a = areas[col] if areas and col < len(areas) else 0.0
                self.register(tuple(input_centroids[col]), a)
                new_det_indices.append(col)

        return self._nid, new_det_indices

    def _greedy_match(self, D: np.ndarray):
        pairs = []
        for r in range(D.shape[0]):
            for c in range(D.shape[1]):
                if D[r, c] < 1e5:
                    pairs.append((D[r, c], r, c))
        pairs.sort()
        matched_r, matched_c = [], []
        used_r, used_c = set(), set()
        for d, r, c in pairs:
            if r not in used_r and c not in used_c:
                matched_r.append(r)
                matched_c.append(c)
                used_r.add(r)
                used_c.add(c)
        return matched_r, matched_c

    def reset(self):
        self.objects.clear()
        self.velocities.clear()
        self.predictions.clear()
        self.disappeared.clear()
        self._grain_areas.clear()
        self._nid = 0


# Alias UniqueGrainTracker to GatedVelocityTracker for full backward compatibility
UniqueGrainTracker = GatedVelocityTracker


class SpikeGuard:
    """Suppress frames with anomalously high detection counts (lighting artifacts)."""

    def __init__(self, window: int = 60, multiplier: float = 3.0, min_threshold: int = 20):
        self._window = deque(maxlen=window)
        self._multiplier = multiplier
        self._min_threshold = min_threshold

    def is_spike(self, count: int) -> bool:
        if len(self._window) < 10:
            self._window.append(count)
            return count > self._min_threshold * 3
        median = float(np.median(self._window))
        threshold = max(self._min_threshold, median * self._multiplier)
        self._window.append(count)
        return count > threshold

    def reset(self):
        self._window.clear()
