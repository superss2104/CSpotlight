DEFAULT_CLIP_LEN_SECONDS = 4
DEFAULT_START_BIAS_SECONDS = -4.0
DEFAULT_MIN_CLIP_GAP_SECONDS = 0.75


def frames_to_timestamps(
    merged_windows,
    fps,
    clip_len=DEFAULT_CLIP_LEN_SECONDS,
    start_bias=DEFAULT_START_BIAS_SECONDS,
):
    timestamps = []

    for start_frame, end_frame in merged_windows:
        event_start = start_frame / fps
        event_end = end_frame / fps
        event_duration = event_end - event_start

        clip_start = max(0, event_start + start_bias)

        if event_duration <= clip_len:
            # Short event — fixed length clip.
            clip_end = clip_start + clip_len
        else:
            # Long event — single continuous clip covering the whole event.
            # Add a small buffer at the end.
            clip_end = event_end + 2.0

        timestamps.append((clip_start, clip_end))

    return timestamps


def merge_overlapping_clips(timestamps, min_gap=DEFAULT_MIN_CLIP_GAP_SECONDS):
    if not timestamps:
        return []

    sorted_timestamps = sorted(timestamps)
    merged = [sorted_timestamps[0]]

    for start, end in sorted_timestamps[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + min_gap:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


