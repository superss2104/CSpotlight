import logging

import numpy as np

LOGGER = logging.getLogger(__name__)
WINDOW_PERCENTILE = 60


def sliding_windows(scores, window_size, step_size):
    windows = []
    i = 0

    while i + window_size <= len(scores):
        window = scores[i : i + window_size]
        window_score = sum(window) / len(window)
        windows.append((i, i + window_size - 1, window_score))
        i += step_size

    if len(scores) >= window_size:
        last_start = len(scores) - window_size
        if not windows or windows[-1][0] != last_start:
            window = scores[last_start:]
            window_score = sum(window) / len(window)
            windows.append((last_start, len(scores) - 1, window_score))

    return windows


def percentile_threshold(windows, percentile=WINDOW_PERCENTILE):
    if not windows:
        return []
    scores = [w[2] for w in windows]
    threshold = np.percentile(scores, percentile)
    highlight_windows = [w for w in windows if w[2] >= threshold]
    LOGGER.info("%d highlight windows detected", len(highlight_windows))
    return highlight_windows


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


def filter_short_events(windows, fps, min_duration_seconds):
    filtered = []
    for start_frame, end_frame in windows:
        duration = (end_frame - start_frame + 1) / fps
        if duration >= min_duration_seconds:
            filtered.append((start_frame, end_frame))
    return filtered
