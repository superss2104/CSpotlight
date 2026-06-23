
import logging
from dataclasses import dataclass, field
from typing import List, Tuple

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class KillfeedConfig:


    # ROI bounds as fractions of the full frame dimensions.
    roi_x_start: float = 0.60
    roi_y_start: float = 0.01
    roi_x_end: float = 0.99
    roi_y_end: float = 0.25

    # HSV thresholds for the red outline.  Red wraps around the hue wheel so
    # we need two ranges.
    red_hue_low: tuple = (0, 100, 100)
    red_hue_low_upper: tuple = (10, 255, 255)
    red_hue_high: tuple = (170, 100, 100)
    red_hue_high_upper: tuple = (180, 255, 255)

    # Defines the minimum size of a kill-feed entry relative to the ROI.
    min_area_ratio: float = 0.005

    # Minimum aspect ratio (width / height) for a valid kill-feed rectangle.
    min_aspect_ratio: float = 3.0

    # Maximum fraction of pixels inside the *full* bounding rect that are
    # red.  Lowered from 0.4 to 0.30 to better reject semi-transparent
    # death fills whose text/icon gaps reduce their apparent fill ratio.
    max_interior_fill: float = 0.30

    # Maximum fill ratio of the *inner region* (excluding the border zone).
    # A true outline has virtually zero coloured pixels in its interior.
    # Filled death entries still have substantial red even with text gaps.
    max_inner_fill: float = 0.10

    # Fraction of the shorter rectangle dimension used as the border zone
    # width when computing the inner-fill ratio.  Minimum 4 px.
    border_zone_ratio: float = 0.15

    # Polygon approximation tolerance (fraction of perimeter).
    approx_epsilon: float = 0.04

    # Maximum vertex count after polygon approximation.  Rectangles with
    # slightly rounded corners may produce 4-8 vertices.
    max_vertices: int = 8

    # Multi-kill score cap.
    max_score: float = 3.0


DEFAULT_CONFIG = KillfeedConfig()


@dataclass
class KillfeedResult:
    """Container for killfeed analysis output.

    Attributes:
        scores:      Per-frame float scores (same as extract_killfeed_scores output).
        kill_counts: Per-frame raw kill counts (number of red outlines detected).
    """
    scores: List[float] = field(default_factory=list)
    kill_counts: List[int] = field(default_factory=list)




def extract_killfeed_scores(video_path, target_length, config=None):
    """Return per-frame killfeed scores aligned to *target_length*.

    This is the original public API and remains unchanged.
    """
    result = extract_killfeed_data(video_path, target_length, config)
    return result.scores


def extract_killfeed_data(video_path, target_length, config=None):
    """Return a :class:`KillfeedResult` with both scores and raw kill counts.

    The *scores* list is identical to what :func:`extract_killfeed_scores`
    returns.  The *kill_counts* list contains the integer number of detected
    red outlines per frame, aligned to *target_length*.
    """
    if target_length <= 0:
        return KillfeedResult()

    if config is None:
        config = DEFAULT_CONFIG

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        LOGGER.warning("Kill-feed detection: failed to open video %s", video_path)
        return KillfeedResult()

    try:
        raw_scores = []
        raw_counts = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            score, count = detect_player_kills_detailed(frame, config)
            raw_scores.append(score)
            raw_counts.append(count)
    finally:
        cap.release()

    if not raw_scores:
        return KillfeedResult()

    aligned_scores = _align_scores(raw_scores, target_length)
    aligned_counts = _align_counts(raw_counts, target_length)
    LOGGER.info("Extracted %d kill-feed scores (max %.2f)", len(aligned_scores), max(aligned_scores))
    return KillfeedResult(scores=aligned_scores, kill_counts=aligned_counts)


def detect_player_kills(frame, config=None):
    """Return the killfeed score for a single frame (float).

    This is the original public API and remains unchanged.
    """
    score, _count = detect_player_kills_detailed(frame, config)
    return score


def detect_player_kills_detailed(frame, config=None):
    """Return ``(score, kill_count)`` for a single frame.

    *score* is identical to :func:`detect_player_kills`.  *kill_count* is the
    raw number of detected red-outlined killfeed entries.
    """
    if config is None:
        config = DEFAULT_CONFIG

    h, w = frame.shape[:2]
    roi = _crop_roi(frame, w, h, config)
    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV) #Converts the Region Of Interest to HSV Color space
    red_mask = _build_red_mask(roi_hsv, config) #Binary mask for red pixels

    outlines = find_red_outlines(red_mask, roi_hsv, config)
    count = len(outlines) #counts detected kill feed entries

    if count == 0:
        return 0.0, 0
    # First kill = 1.0, each additional adds 0.5, capped.
    score = min(1.0 + 0.5 * (count - 1), config.max_score)
    return score, count



def _crop_roi(frame, frame_w, frame_h, config):
    #Crop the kill-feed region of interest from the full frame
    x1 = int(frame_w * config.roi_x_start)
    y1 = int(frame_h * config.roi_y_start)
    x2 = int(frame_w * config.roi_x_end)
    y2 = int(frame_h * config.roi_y_end)
    return frame[y1:y2, x1:x2]


def _build_red_mask(hsv_roi, config):
    #Create a binary mask of red-hue pixels in the ROI
    mask_low = cv2.inRange(
        hsv_roi,
        np.array(config.red_hue_low, dtype=np.uint8),
        np.array(config.red_hue_low_upper, dtype=np.uint8),
    )
    mask_high = cv2.inRange(
        hsv_roi,
        np.array(config.red_hue_high, dtype=np.uint8),
        np.array(config.red_hue_high_upper, dtype=np.uint8),
    )
    return mask_low | mask_high


def find_red_outlines(red_mask, roi_hsv, config):
    
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    roi_h, roi_w = red_mask.shape[:2]
    roi_area = roi_h * roi_w
    min_area = roi_area * config.min_area_ratio

    valid = []
    for contour in contours:
        if not is_hollow_rectangle(contour, red_mask, min_area, config):
            continue
        valid.append(contour)

    return valid


def is_hollow_rectangle(contour, red_mask, min_area, config):
    """Check whether *contour* is a hollow rectangle (kill outline).

    Applies two fill checks:
    1. **Overall fill** — fraction of coloured pixels in the full bounding
       rect.  Must be <= ``max_interior_fill``.
    2. **Inner fill** — fraction of coloured pixels in the interior region
       (excluding the border zone).  Must be <= ``max_inner_fill``.
       This distinguishes true outlines from *filled* death entries whose
       overlaid text/icons create gaps that lower the overall fill ratio.
    """
    area = cv2.contourArea(contour)
    if area < min_area:
        return False

    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False

    approx = cv2.approxPolyDP(contour, config.approx_epsilon * perimeter, True)
    if len(approx) > config.max_vertices:
        return False

    x, y, w, h = cv2.boundingRect(contour)
    if h == 0:
        return False

    aspect = w / h
    if aspect < config.min_aspect_ratio:
        return False

    # --- Overall fill check ---
    interior = red_mask[y:y + h, x:x + w]
    if interior.size == 0:
        return False

    fill_ratio = np.count_nonzero(interior) / interior.size
    if fill_ratio > config.max_interior_fill:
        return False

    # --- Inner fill check ---
    # Sample only the interior region (away from edges).  A true outline
    # has virtually zero coloured pixels here; a filled death entry still
    # has substantial red even with text/icon gaps.
    border = max(4, int(min(w, h) * config.border_zone_ratio))
    inner_y1 = y + border
    inner_y2 = y + h - border
    inner_x1 = x + border
    inner_x2 = x + w - border

    if inner_y2 > inner_y1 and inner_x2 > inner_x1:
        inner = red_mask[inner_y1:inner_y2, inner_x1:inner_x2]
        if inner.size > 0:
            inner_fill = np.count_nonzero(inner) / inner.size
            if inner_fill > config.max_inner_fill:
                return False

    return True


def _align_scores(raw_scores, target_length):
   
    n = len(raw_scores)
    if n == target_length:
        return raw_scores
    if n == 0:
        return [0.0] * target_length

    aligned = []
    for i in range(target_length):
        src_idx = int(round(i * (n - 1) / max(1, target_length - 1)))
        src_idx = min(src_idx, n - 1)
        aligned.append(raw_scores[src_idx])
    return aligned


def _align_counts(raw_counts, target_length):
    """Align integer kill counts to *target_length* (nearest-neighbour)."""
    n = len(raw_counts)
    if n == target_length:
        return raw_counts
    if n == 0:
        return [0] * target_length

    aligned = []
    for i in range(target_length):
        src_idx = int(round(i * (n - 1) / max(1, target_length - 1)))
        src_idx = min(src_idx, n - 1)
        aligned.append(raw_counts[src_idx])
    return aligned
