import logging

try:
    from ..audio.analysis import extract_audio_scores
    from ..cs2.killfeed import extract_killfeed_scores
    from ..video.motion import extract_motion_scores
    from .scoring import combine_multiple_scores, combine_scores, normalize_scores
    from .timestamps import (
        DEFAULT_CLIP_LEN_SECONDS,
        DEFAULT_MIN_CLIP_GAP_SECONDS,
        DEFAULT_START_BIAS_SECONDS,
        frames_to_timestamps,
        suppress_overlapping_clips_by_score,
    )
    from .windows import filter_short_events, merge_windows, percentile_threshold, sliding_windows
except ImportError:  # Support running src/main.py directly.
    from audio.analysis import extract_audio_scores
    from cs2.killfeed import extract_killfeed_scores
    from highlight.scoring import combine_multiple_scores, combine_scores, normalize_scores
    from highlight.timestamps import (
        DEFAULT_CLIP_LEN_SECONDS,
        DEFAULT_MIN_CLIP_GAP_SECONDS,
        DEFAULT_START_BIAS_SECONDS,
        frames_to_timestamps,
        suppress_overlapping_clips_by_score,
    )
    from highlight.windows import filter_short_events, merge_windows, percentile_threshold, sliding_windows
    from video.motion import extract_motion_scores

LOGGER = logging.getLogger(__name__)
WINDOW_STEP_FRAMES = 5
WINDOW_PERCENTILE = 50
MIN_EVENT_DURATION_SECONDS = 0.1
MERGE_GAP_SECONDS = 0.6
MOTION_SCORE_WEIGHT = 0.25
AUDIO_SCORE_WEIGHT = 0.25
KILLFEED_SCORE_WEIGHT = 0.5


def detect_highlights(video_path, motion_weight=None, audio_weight=None, killfeed_weight=None):
    motion_scores, fps = extract_motion_scores(video_path)
    scores = build_highlight_scores(
        video_path, motion_scores, fps,
        motion_weight, audio_weight, killfeed_weight,
    )

    window_size = max(1, int(round(fps)))
    windows = sliding_windows(scores, window_size, WINDOW_STEP_FRAMES)
    highlight_windows = percentile_threshold(windows, percentile=WINDOW_PERCENTILE)
    merge_gap_frames = max(1, int(round(fps * MERGE_GAP_SECONDS)))
    merged = merge_windows(highlight_windows, max_gap=merge_gap_frames)
    filtered = filter_short_events(merged, fps, MIN_EVENT_DURATION_SECONDS)

    timestamps = frames_to_timestamps(
        filtered,
        fps,
        clip_len=DEFAULT_CLIP_LEN_SECONDS,
        start_bias=DEFAULT_START_BIAS_SECONDS,
    )
    clip_scores = score_clips(timestamps, highlight_windows, fps)
    return suppress_overlapping_clips_by_score(
        timestamps,
        clip_scores,
        min_gap=DEFAULT_MIN_CLIP_GAP_SECONDS,
    )


def build_highlight_scores(
    video_path, motion_scores, fps,
    motion_weight=None, audio_weight=None, killfeed_weight=None,
):
    if motion_weight is None:
        motion_weight = MOTION_SCORE_WEIGHT
    if audio_weight is None:
        audio_weight = AUDIO_SCORE_WEIGHT
    if killfeed_weight is None:
        killfeed_weight = KILLFEED_SCORE_WEIGHT

    audio_scores = _extract_audio_safe(video_path, fps, len(motion_scores))
    killfeed_scores = _extract_killfeed_safe(video_path, len(motion_scores))

    signals = [motion_scores]
    weights = [motion_weight]
    signal_names = ["motion"]

    if audio_scores:
        signals.append(audio_scores)
        weights.append(audio_weight)
        signal_names.append("audio")

    if killfeed_scores:
        signals.append(killfeed_scores)
        weights.append(killfeed_weight)
        signal_names.append("killfeed")

    if len(signals) == 1:
        LOGGER.info("Using motion-only highlight scores")
        return motion_scores

    LOGGER.info(
        "Combining %s scores with weights %s",
        " + ".join(signal_names),
        " / ".join(f"{w:.2f}" for w in weights),
    )

    combined_scores = combine_multiple_scores(signals, weights)

    # --- Killfeed gate ---------------------------------------------------
    # Zero out any frame where the killfeed signal is absent.  This ensures
    # that high motion / audio alone (e.g. scoping in) cannot produce a
    # highlight — a kill-feed entry must be present.
    if killfeed_scores:
        norm_kf = normalize_scores(killfeed_scores)
        gated = 0
        for i in range(len(combined_scores)):
            kf_val = norm_kf[i] if i < len(norm_kf) else 0.0
            if kf_val == 0.0:
                combined_scores[i] = 0.0
                gated += 1
        LOGGER.info(
            "Killfeed gate: zeroed %d / %d frames without kill-feed activity",
            gated, len(combined_scores),
        )

    _log_score_ranges(motion_scores, audio_scores, killfeed_scores, combined_scores)
    return combined_scores


def score_events(events, scored_windows):
    event_scores = []
    for event_start, event_end in events:
        overlapping_scores = [
            score
            for window_start, window_end, score in scored_windows
            if window_start <= event_end and event_start <= window_end
        ]
        event_scores.append(max(overlapping_scores, default=0.0))
    return event_scores


def score_clips(timestamps, scored_windows, fps):
    """Score each clip timestamp by the max highlight-window score it overlaps."""
    clip_scores = []
    for clip_start, clip_end in timestamps:
        start_frame = int(clip_start * fps)
        end_frame = int(clip_end * fps)
        overlapping = [
            score
            for w_start, w_end, score in scored_windows
            if w_start <= end_frame and start_frame <= w_end
        ]
        clip_scores.append(max(overlapping, default=0.0))
    return clip_scores


# ---------------------------------------------------------------------------
# Safe extraction helpers
# ---------------------------------------------------------------------------

def _extract_audio_safe(video_path, fps, target_length):
    try:
        return extract_audio_scores(video_path, fps, target_length=target_length)
    except Exception:
        LOGGER.exception(
            "Unexpected audio analysis failure for %s. Falling back without audio.",
            video_path,
        )
        return []


def _extract_killfeed_safe(video_path, target_length):
    try:
        scores = extract_killfeed_scores(video_path, target_length)
        return scores
    except Exception:
        LOGGER.exception(
            "Unexpected kill-feed analysis failure for %s. Falling back without kill-feed.",
            video_path,
        )
        return []


def _log_score_ranges(motion_scores, audio_scores, killfeed_scores, combined_scores):
    parts = [
        f"motion: {min(motion_scores):.4f}..{max(motion_scores):.4f}",
    ]
    if audio_scores:
        parts.append(f"audio: {min(audio_scores):.4f}..{max(audio_scores):.4f}")
    if killfeed_scores:
        parts.append(f"killfeed: {min(killfeed_scores):.4f}..{max(killfeed_scores):.4f}")
    parts.append(f"combined: {min(combined_scores):.4f}..{max(combined_scores):.4f}")
    LOGGER.info("Score ranges - %s", ", ".join(parts))
