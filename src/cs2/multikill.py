"""Multikill event detection from per-frame kill-count data.

A *multikill* is defined as two or more kills registered by the player
within a sliding time window (default 5 seconds).  The module provides
two main entry points:

* :func:`detect_multikill_events` — returns discrete event objects.
* :func:`build_multikill_mask` — returns a per-frame boolean mask that
  the pipeline can use for clip categorization.

Detection uses **rising-edge analysis with debounce** to avoid counting
a single flickering killfeed outline as multiple kills.
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple

LOGGER = logging.getLogger(__name__)

DEFAULT_MULTIKILL_WINDOW_SECONDS = 5.0

# Minimum gap between rising edges to consider them as distinct kills.
# The killfeed outline detector is noisy — a single persistent entry can
# flicker in and out, producing spurious 0→1 transitions.  Any rising
# edge within this cooldown of the previous one is treated as the same
# kill re-appearing and is suppressed.
DEBOUNCE_COOLDOWN_SECONDS = 1.0


@dataclass
class MultikillEvent:
    """A contiguous range of frames that belong to a multikill sequence.

    Attributes:
        start_frame: First frame index of the multikill window.
        end_frame:   Last frame index of the multikill window (inclusive).
        total_kills: Accumulated kill count within the window.
    """
    start_frame: int
    end_frame: int
    total_kills: int


def detect_multikill_events(
    kill_counts: List[int],
    fps: float,
    time_window: float = DEFAULT_MULTIKILL_WINDOW_SECONDS,
) -> List[MultikillEvent]:
    """Detect multikill events from per-frame kill counts.

    A killfeed entry persists on screen for several seconds, so the raw
    per-frame count cannot be summed directly — that would count the same
    kill many times.  Instead, this function detects **rising edges**:
    frames where the kill count *increases* from the previous frame,
    indicating a genuinely new kill appeared in the killfeed.

    Those distinct kill events are then grouped within *time_window*
    seconds.  If a group contains >= 2 distinct kills, it becomes a
    :class:`MultikillEvent`.

    Parameters
    ----------
    kill_counts : list[int]
        Per-frame kill counts (aligned to video frames).
    fps : float
        Video frame rate.
    time_window : float
        Duration in seconds of the sliding accumulation window.

    Returns
    -------
    list[MultikillEvent]
        Detected multikill events sorted chronologically.
    """
    if not kill_counts or fps <= 0:
        return []

    window_frames = max(1, int(round(fps * time_window)))
    cooldown_frames = max(1, int(round(fps * DEBOUNCE_COOLDOWN_SECONDS)))
    num_frames = len(kill_counts)

    # --- Rising-edge detection with debounce ---
    # A "kill event" is a frame where the count increases from the previous
    # frame.  Each increase of +N represents N new kills appearing.
    #
    # However, the killfeed outline detector is noisy — a single entry can
    # flicker (1→0→1→0→1) across consecutive frames.  Each 0→1 transition
    # would naively look like a new kill.  To prevent this, we apply a
    # cooldown: after recording a rising edge, we suppress any further
    # rising edges within DEBOUNCE_COOLDOWN_SECONDS.
    raw_edges: List[Tuple[int, int]] = []  # (frame_index, delta)
    prev = 0
    for i, count in enumerate(kill_counts):
        if count > prev:
            raw_edges.append((i, count - prev))
        prev = count

    if not raw_edges:
        return []

    # Apply debounce: only keep edges that are >= cooldown_frames apart.
    kill_events: List[Tuple[int, int]] = [raw_edges[0]]
    for frame, delta in raw_edges[1:]:
        last_frame, last_delta = kill_events[-1]
        if frame - last_frame >= cooldown_frames:
            # Far enough apart — this is a genuinely new kill.
            kill_events.append((frame, delta))
        else:
            # Within cooldown — same kill flickering.  Absorb it.
            LOGGER.debug(
                "Debounce: suppressed rising edge at frame %d "
                "(only %d frames after previous at %d)",
                frame, frame - last_frame, last_frame,
            )

    total_distinct = sum(n for _, n in kill_events)
    if total_distinct < 2:
        return []

    # --- Group kill events within the sliding time window ---
    events: List[MultikillEvent] = []
    i = 0
    while i < len(kill_events):
        group_start_frame, group_kills = kill_events[i]
        group_end_frame = group_start_frame
        j = i + 1

        # Extend the group as long as the next kill event falls within
        # *window_frames* of the group start.
        while j < len(kill_events):
            candidate_frame, candidate_kills = kill_events[j]
            if candidate_frame - group_start_frame <= window_frames:
                group_end_frame = candidate_frame
                group_kills += candidate_kills
                j += 1
            else:
                break

        if group_kills >= 2:
            events.append(MultikillEvent(
                start_frame=group_start_frame,
                end_frame=group_end_frame,
                total_kills=group_kills,
            ))
            i = j  # skip past all events consumed by this group
        else:
            i += 1

    # Merge overlapping / adjacent events.
    if len(events) > 1:
        merged: List[MultikillEvent] = [events[0]]
        for ev in events[1:]:
            prev_ev = merged[-1]
            if ev.start_frame <= prev_ev.end_frame + window_frames:
                merged[-1] = MultikillEvent(
                    start_frame=prev_ev.start_frame,
                    end_frame=max(prev_ev.end_frame, ev.end_frame),
                    total_kills=prev_ev.total_kills + ev.total_kills,
                )
            else:
                merged.append(ev)
        events = merged

    LOGGER.info(
        "Detected %d multikill event(s) from %d frames (%d distinct kill appearances)",
        len(events), num_frames, len(kill_events),
    )
    return events


def build_multikill_mask(
    kill_counts: List[int],
    fps: float,
    time_window: float = DEFAULT_MULTIKILL_WINDOW_SECONDS,
) -> List[bool]:
    """Return a per-frame boolean mask marking multikill frames.

    A frame is ``True`` if it falls within any :class:`MultikillEvent`
    detected by :func:`detect_multikill_events`.

    The returned list has the same length as *kill_counts*.
    """
    num_frames = len(kill_counts)
    if num_frames == 0:
        return []

    events = detect_multikill_events(kill_counts, fps, time_window)
    mask = [False] * num_frames

    for ev in events:
        for i in range(ev.start_frame, min(ev.end_frame + 1, num_frames)):
            mask[i] = True

    return mask
