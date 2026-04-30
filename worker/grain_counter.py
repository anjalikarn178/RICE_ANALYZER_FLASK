"""
Grain detection and unique-ID tracking for real-time rice analysis.
Adapted from count_grains_updated.py (centroid tracking, Hungarian matching).
"""

import cv2
import numpy as np
from collections import deque
from typing import List, Optional, Tuple

try:
    from scipy.optimize import linear_sum_assignment
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


BROKEN_AREA_THRESHOLD = 300  # px² — grains below this are broken


def _make_mask(frame: np.ndarray, mode: str = "auto") -> np.ndarray:
    """Build a binary mask isolating grain pixels via belt-background subtraction."""
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
) -> Tuple[list, np.ndarray]:
    """
    Detect grain contours in frame.
    Returns (valid_contours, binary_mask).
    Filters: area range, border-touching blobs (belt artifacts).
    """
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
        valid.append(c)
    return valid, mask


class UniqueGrainTracker:
    """
    Track grain centroids frame-to-frame, counting each grain exactly once.

    update() returns (total_unique_count, new_detection_indices) where
    new_detection_indices are indices into the centroids list for grains
    seen for the first time in this frame.
    """

    def __init__(self, max_dist: int = 45, max_missed: int = 3):
        self.max_dist   = max_dist
        self.max_missed = max_missed
        self._tracks: dict = {}       # id → {"centroid": (x,y), "missed": int}
        self._grain_areas: dict = {}  # id → max area seen
        self._nid = 0                 # total unique grains ever assigned

    def _match_hungarian(self, dets: list):
        if not self._tracks or not dets:
            return {}, set()

        track_ids = list(self._tracks.keys())
        cost = np.full((len(track_ids), len(dets)), 1e9, dtype=np.float64)
        for ti, tid in enumerate(track_ids):
            tx, ty = self._tracks[tid]["centroid"]
            for di, (cx, cy) in enumerate(dets):
                d = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
                if d <= self.max_dist:
                    cost[ti, di] = d

        if _HAS_SCIPY:
            row_ind, col_ind = linear_sum_assignment(cost)
            matched_t, matched_d = {}, set()
            for ti, di in zip(row_ind, col_ind):
                if cost[ti, di] < 1e8:
                    matched_t[track_ids[ti]] = di
                    matched_d.add(di)
            return matched_t, matched_d
        else:
            return self._match_greedy(dets)

    def _match_greedy(self, dets: list):
        matched_t, matched_d = {}, set()
        pairs = []
        for tid, t in self._tracks.items():
            tx, ty = t["centroid"]
            for di, (cx, cy) in enumerate(dets):
                d = ((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5
                if d <= self.max_dist:
                    pairs.append((d, tid, di))
        pairs.sort()
        for d, tid, di in pairs:
            if tid not in matched_t and di not in matched_d:
                matched_t[tid] = di
                matched_d.add(di)
        return matched_t, matched_d

    def update(self, centroids: list, areas: Optional[list] = None) -> Tuple[int, list]:
        """
        Update tracker with this frame's detections.

        Returns
        -------
        (total_unique_count, new_detection_indices)
            new_detection_indices: indices into `centroids` for newly seen grains.
        """
        matched_t, matched_d = self._match_hungarian(centroids)

        for tid, di in matched_t.items():
            self._tracks[tid]["centroid"] = centroids[di]
            self._tracks[tid]["missed"]   = 0
            if areas and di < len(areas):
                self._grain_areas[tid] = max(self._grain_areas.get(tid, 0), areas[di])

        for tid in list(self._tracks):
            if tid not in matched_t:
                self._tracks[tid]["missed"] += 1

        new_det_indices = []
        for di, c in enumerate(centroids):
            if di not in matched_d:
                a = areas[di] if areas and di < len(areas) else 0
                self._tracks[self._nid] = {"centroid": c, "missed": 0}
                self._grain_areas[self._nid] = a
                new_det_indices.append(di)
                self._nid += 1

        self._tracks = {
            k: v for k, v in self._tracks.items()
            if v["missed"] <= self.max_missed
        }

        return self._nid, new_det_indices

    def reset(self):
        self._tracks = {}
        self._grain_areas = {}
        self._nid = 0


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
