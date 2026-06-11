
import logging
from dataclasses import dataclass, field

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

    # Minimum contour area as a fraction of the ROI area.
    min_area_ratio: float = 0.005

    # Minimum aspect ratio (width / height) for a valid kill-feed rectangle.
    min_aspect_ratio: float = 3.0

    # Maximum fraction of pixels inside the bounding rect that are red.  A
    # true outline has a low interior fill; solid red UI elements are rejected.
    max_interior_fill: float = 0.4

    # Polygon approximation tolerance (fraction of perimeter).
    approx_epsilon: float = 0.04

    # Maximum vertex count after polygon approximation.  Rectangles with
    # slightly rounded corners may produce 4-8 vertices.
    max_vertices: int = 8

    # Multi-kill score cap.
    max_score: float = 3.0


DEFAULT_CONFIG = KillfeedConfig()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_killfeed_scores(video_path, target_length, config=None):
   
    if target_length <= 0:
        return []

    if config is None:
        config = DEFAULT_CONFIG

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        LOGGER.warning("Kill-feed detection: failed to open video %s", video_path)
        return []

    try:
        raw_scores = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            raw_scores.append(detect_player_kills(frame, config))
    finally:
        cap.release()

    if not raw_scores:
        return []

    aligned = _align_scores(raw_scores, target_length)
    LOGGER.info("Extracted %d kill-feed scores (max %.2f)", len(aligned), max(aligned))
    return aligned


def detect_player_kills(frame, config=None):
   
    if config is None:
        config = DEFAULT_CONFIG

    h, w = frame.shape[:2]
    roi = _crop_roi(frame, w, h, config)
    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    red_mask = _build_red_mask(roi_hsv, config)

    outlines = find_red_outlines(red_mask, roi_hsv, config)
    count = len(outlines)

    if count == 0:
        return 0.0
    # First kill = 1.0, each additional adds 0.5, capped.
    return min(1.0 + 0.5 * (count - 1), config.max_score)



def _crop_roi(frame, frame_w, frame_h, config):
    """Crop the kill-feed region of interest from the full frame."""
    x1 = int(frame_w * config.roi_x_start)
    y1 = int(frame_h * config.roi_y_start)
    x2 = int(frame_w * config.roi_x_end)
    y2 = int(frame_h * config.roi_y_end)
    return frame[y1:y2, x1:x2]


def _build_red_mask(hsv_roi, config):
    """Create a binary mask of red-hue pixels in the ROI."""
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

    # Hollow check: the interior of the bounding rect should have a low
    # fraction of red pixels compared to the rect area.
    interior = red_mask[y:y + h, x:x + w]
    if interior.size == 0:
        return False

    fill_ratio = np.count_nonzero(interior) / interior.size
    if fill_ratio > config.max_interior_fill:
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
