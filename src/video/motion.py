import logging
import os
import subprocess

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)
WINDOW_STEP_FRAMES = 10
WINDOW_PERCENTILE = 60
MIN_EVENT_DURATION_SECONDS = 0.8
DEFAULT_CLIP_LEN_SECONDS = 8.0
DEFAULT_START_BIAS_SECONDS = 0.25
DEFAULT_MIN_CLIP_GAP_SECONDS = 0.75
MERGE_GAP_SECONDS = 0.5


def detect_highlights(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video file: {video_path}")

    try:
        prev_blurred = None
        motion_scores = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            current_blurred = cv2.GaussianBlur(edges, (9, 9), 0)

            if prev_blurred is not None:
                diff = cv2.absdiff(current_blurred, prev_blurred)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

                h, w = thresh.shape
                grid_h, grid_w = 4, 4
                cell_h = h // grid_h
                cell_w = w // grid_w

                cell_scores = []
                for i in range(grid_h):
                    for j in range(grid_w):
                        cell = thresh[i * cell_h : (i + 1) * cell_h, j * cell_w : (j + 1) * cell_w]
                        cell_scores.append(cell.mean())

                motion_scores.append(max(cell_scores))

            prev_blurred = current_blurred

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            LOGGER.warning("Invalid FPS metadata (%s) for %s. Falling back to 30 FPS.", fps, video_path)
            fps = 30.0

        window_size = max(1, int(round(fps)))
        windows = sliding_windows(motion_scores, window_size, WINDOW_STEP_FRAMES)
        highlight_windows = percentile_threshold(windows, percentile=WINDOW_PERCENTILE)
        merge_gap_frames = max(1, int(round(fps * MERGE_GAP_SECONDS)))
        merged = merge_windows(highlight_windows, max_gap=merge_gap_frames)

        filtered = []
        for start_frame, end_frame in merged:
            duration = (end_frame - start_frame + 1) / fps
            if duration >= MIN_EVENT_DURATION_SECONDS:
                filtered.append((start_frame, end_frame))

        timestamps = frames_to_timestamps(
            filtered,
            fps,
            clip_len=DEFAULT_CLIP_LEN_SECONDS,
            start_bias=DEFAULT_START_BIAS_SECONDS,
        )
        return suppress_overlapping_clips(timestamps, min_gap=DEFAULT_MIN_CLIP_GAP_SECONDS)
    finally:
        cap.release()
        cv2.destroyAllWindows()


def percentile_threshold(windows, percentile=WINDOW_PERCENTILE):
    if not windows:
        return []
    scores = [w[2] for w in windows]
    threshold = np.percentile(scores, percentile)
    highlight_windows = [w for w in windows if w[2] >= threshold]
    LOGGER.info("%d highlight windows detected", len(highlight_windows))
    return highlight_windows


def sliding_windows(motion_scores, window_size, step_size):
    windows = []
    i = 0

    while i + window_size <= len(motion_scores):
        window = motion_scores[i : i + window_size]
        window_score = sum(window) / len(window)
        windows.append((i, i + window_size - 1, window_score))
        i += step_size

    if len(motion_scores) >= window_size:
        last_start = len(motion_scores) - window_size
        if not windows or windows[-1][0] != last_start:
            window = motion_scores[last_start:]
            window_score = sum(window) / len(window)
            windows.append((last_start, len(motion_scores) - 1, window_score))

    return windows


def merge_windows(windows, max_gap=0):
    if not windows:
        return []

    merged = []
    current_start, current_end = windows[0][:2]
    for window in windows[1:]:
        next_start, next_end = window[:2]
        if next_start <= current_end + max_gap:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    merged.append((current_start, current_end))
    return merged


def frames_to_timestamps(
    merged_windows,
    fps,
    clip_len=DEFAULT_CLIP_LEN_SECONDS,
    start_bias=DEFAULT_START_BIAS_SECONDS,
):
    timestamps = []
    half = clip_len / 2

    for start_frame, end_frame in merged_windows:
        center = (start_frame + end_frame) // 2
        start_time = max(0, center / fps - half + start_bias)
        end_time = center / fps + half
        timestamps.append((start_time, end_time))

    return timestamps


def cut_clips(video_path, timestamps, output_dir="clips"):
    os.makedirs(output_dir, exist_ok=True)

    for idx, (start, end) in enumerate(timestamps):
        output_path = os.path.join(output_dir, f"clip_{idx + 1}.mp4")
        command = [
            "ffmpeg",
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            video_path,
            "-c",
            "copy",
            output_path,
            "-y",
        ]
        subprocess.run(command, check=True)


def suppress_overlapping_clips(timestamps, min_gap=DEFAULT_MIN_CLIP_GAP_SECONDS):
    if not timestamps:
        return []

    sorted_timestamps = sorted(timestamps)
    filtered = [sorted_timestamps[0]]

    for start, end in sorted_timestamps[1:]:
        _, last_end = filtered[-1]
        if start <= last_end + min_gap:
            continue
        filtered.append((start, end))

    return filtered
