DEFAULT_CLIP_LEN_SECONDS = 8.0
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
        if any(_clips_overlap_too_much(timestamp, kept_ts, min_gap) for kept_ts in kept):
            continue
        kept.append(timestamp)

    return sorted(kept)


def _clips_overlap_too_much(first, second, min_gap):
    """Return True if *first* and *second* overlap by more than half the
    shorter clip's duration, or if they are separated by less than *min_gap*.
    """
    first_start, first_end = first
    second_start, second_end = second

    # No overlap at all and separated by enough gap -> keep both.
    if first_start > second_end + min_gap or second_start > first_end + min_gap:
        return False

    # Compute the overlap as a fraction of the shorter clip's duration.
    overlap_start = max(first_start, second_start)
    overlap_end = min(first_end, second_end)
    overlap = max(0.0, overlap_end - overlap_start)

    shorter_duration = min(first_end - first_start, second_end - second_start)
    if shorter_duration <= 0:
        return True

    return overlap / shorter_duration > 0.5


def _clips_overlap_or_touch(first, second, min_gap):
    first_start, first_end = first
    second_start, second_end = second
    return first_start <= second_end + min_gap and second_start <= first_end + min_gap

