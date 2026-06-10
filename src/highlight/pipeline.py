import logging

try:
    from ..audio.analysis import extract_audio_scores
    from ..video.motion import extract_motion_scores
    from .scoring import combine_scores
    from .timestamps import frames_to_timestamps, suppress_overlapping_clips_by_score
    from .windows import filter_short_events, merge_windows, percentile_threshold, sliding_windows
except ImportError:  # Support running src/main.py directly.
    from audio.analysis import extract_audio_scores
    from highlight.scoring import combine_scores
    from highlight.timestamps import frames_to_timestamps, suppress_overlapping_clips_by_score
    from highlight.windows import filter_short_events, merge_windows, percentile_threshold, sliding_windows
    from video.motion import extract_motion_scores

LOGGER = logging.getLogger(__name__)
WINDOW_STEP_FRAMES = 10
WINDOW_PERCENTILE = 60
MIN_EVENT_DURATION_SECONDS = 0.5
DEFAULT_CLIP_LEN_SECONDS = 8.0
DEFAULT_START_BIAS_SECONDS = 0.25
DEFAULT_MIN_CLIP_GAP_SECONDS = 0.75
MERGE_GAP_SECONDS = 1
MOTION_SCORE_WEIGHT = 0.7
AUDIO_SCORE_WEIGHT = 0.3


def detect_highlights(video_path, motion_weight=None, audio_weight=None):
    motion_scores, fps = extract_motion_scores(video_path)
    scores = build_highlight_scores(video_path, motion_scores, fps, motion_weight, audio_weight)

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
    event_scores = score_events(filtered, highlight_windows)
    return suppress_overlapping_clips_by_score(
        timestamps,
        event_scores,
        min_gap=DEFAULT_MIN_CLIP_GAP_SECONDS,
    )


def build_highlight_scores(video_path, motion_scores, fps, motion_weight=None, audio_weight=None):
    if motion_weight is None:
        motion_weight = MOTION_SCORE_WEIGHT
    if audio_weight is None:
        audio_weight = AUDIO_SCORE_WEIGHT

    try:
        audio_scores = extract_audio_scores(video_path, fps, target_length=len(motion_scores))
    except Exception:
        LOGGER.exception("Unexpected audio analysis failure for %s. Falling back to motion-only scores.", video_path)
        audio_scores = []

    if not audio_scores:
        LOGGER.info("Using motion-only highlight scores")
        return motion_scores

    LOGGER.info(
        "Combining motion and audio scores with weights %.2f / %.2f",
        motion_weight,
        audio_weight,
    )
    combined_scores = combine_scores(
        motion_scores,
        audio_scores,
        primary_weight=motion_weight,
        secondary_weight=audio_weight,
    )
    LOGGER.info(
        "Score ranges - motion: %.4f..%.4f, audio: %.4f..%.4f, combined: %.4f..%.4f",
        min(motion_scores),
        max(motion_scores),
        min(audio_scores),
        max(audio_scores),
        min(combined_scores),
        max(combined_scores),
    )
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
