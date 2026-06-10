DEFAULT_CLIP_LEN_SECONDS = 8.0
DEFAULT_START_BIAS_SECONDS = 0.25
DEFAULT_MIN_CLIP_GAP_SECONDS = 0.75


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


def suppress_overlapping_clips_by_score(timestamps, scores, min_gap=DEFAULT_MIN_CLIP_GAP_SECONDS):
    if not timestamps:
        return []
    if len(timestamps) != len(scores):
        raise ValueError("timestamps and scores must have the same length")

    candidates = sorted(
        zip(timestamps, scores),
        key=lambda item: item[1],
        reverse=True,
    )
    kept = []

    for timestamp, _ in candidates:
        if any(_clips_overlap_or_touch(timestamp, kept_timestamp, min_gap) for kept_timestamp in kept):
            continue
        kept.append(timestamp)

    return sorted(kept)


def _clips_overlap_or_touch(first, second, min_gap):
    first_start, first_end = first
    second_start, second_end = second
    return first_start <= second_end + min_gap and second_start <= first_end + min_gap
