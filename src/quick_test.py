"""Save a diagnostic visualization of what the killfeed detector sees."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import cv2
import numpy as np
from cs2.killfeed import KillfeedConfig, _crop_roi, _build_red_mask, find_red_outlines

VIDEO = os.path.join(os.path.dirname(__file__), "video", "videos", "video.mp4")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "clips", "debug")
os.makedirs(OUT_DIR, exist_ok=True)

config = KillfeedConfig()
cap = cv2.VideoCapture(VIDEO)

# Sample frames where detections were found: 250, 1800, 1950
sample_frames = [250, 500, 1800, 1950]

for target_frame in sample_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    if not ret:
        continue

    h, w = frame.shape[:2]
    roi = _crop_roi(frame, w, h, config)
    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    red_mask = _build_red_mask(roi_hsv, config)

    # Find ALL contours (before hollow check)
    contours_all, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Find valid outlines (after hollow check)
    outlines = find_red_outlines(red_mask, roi_hsv, config)

    # Draw visualizations
    vis_roi = roi.copy()
    vis_mask = cv2.cvtColor(red_mask, cv2.COLOR_GRAY2BGR)

    # Draw ALL contours in blue
    cv2.drawContours(vis_roi, contours_all, -1, (255, 0, 0), 1)
    # Draw ACCEPTED outlines in green (thick)
    cv2.drawContours(vis_roi, outlines, -1, (0, 255, 0), 2)

    # Add info text
    cv2.putText(vis_roi, f"Frame {target_frame}: {len(contours_all)} contours, {len(outlines)} accepted",
                (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    # For each accepted outline, show bounding rect and fill info
    for i, outline in enumerate(outlines):
        x, y, ow, oh = cv2.boundingRect(outline)
        interior = red_mask[y:y+oh, x:x+ow]
        fill = np.count_nonzero(interior) / interior.size if interior.size > 0 else 0

        border = max(4, int(min(ow, oh) * config.border_zone_ratio))
        iy1, iy2 = y + border, y + oh - border
        ix1, ix2 = x + border, x + ow - border
        inner_fill = 0.0
        if iy2 > iy1 and ix2 > ix1:
            inner = red_mask[iy1:iy2, ix1:ix2]
            if inner.size > 0:
                inner_fill = np.count_nonzero(inner) / inner.size

        cv2.putText(vis_roi, f"#{i}: {ow}x{oh} fill={fill:.2f} inner={inner_fill:.2f}",
                    (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

    # Save side by side
    combined = np.hstack([vis_roi, vis_mask])
    path = os.path.join(OUT_DIR, f"frame_{target_frame}.png")
    cv2.imwrite(path, combined)
    print(f"Saved {path}", flush=True)

cap.release()
print("DONE", flush=True)
