"""Clip categorization and filtering.

Provides an enum-based category system and utilities to tag each clip
with a category (single kill vs. multiple kills) and filter clips by
user-selected categories.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Set


class ClipCategory(Enum):
    """Category assigned to a detected highlight clip."""
    SINGLE_KILL = auto()
    MULTIPLE_KILLS = auto()


@dataclass
class CategorizedClip:
    """A highlight clip with an associated category.

    Supports tuple unpacking ``(start, end) = clip`` for backwards
    compatibility with code that expects plain timestamp tuples.
    """
    start: float
    end: float
    category: ClipCategory

    # Allow tuple-style unpacking: start, end = clip
    def __iter__(self):
        return iter((self.start, self.end))

    # Allow indexed access: clip[0], clip[1]
    def __getitem__(self, index):
        return (self.start, self.end)[index]

    def __len__(self):
        return 2


def categorize_clips(
    timestamps: List[tuple],
    multikill_mask: List[bool],
    fps: float,
) -> List[CategorizedClip]:
    """Assign a :class:`ClipCategory` to each clip timestamp.

    For each ``(start, end)`` pair, checks whether any frame within that
    time range is marked as a multikill frame in *multikill_mask*.  If so,
    the clip is categorised as ``MULTIPLE_KILLS``; otherwise ``SINGLE_KILL``.

    Parameters
    ----------
    timestamps : list[tuple[float, float]]
        Clip start/end times in seconds.
    multikill_mask : list[bool]
        Per-frame boolean mask from :func:`build_multikill_mask`.
    fps : float
        Video frame rate (used to convert seconds → frame indices).

    Returns
    -------
    list[CategorizedClip]
    """
    if not timestamps:
        return []

    categorized: List[CategorizedClip] = []
    num_frames = len(multikill_mask)

    for start, end in timestamps:
        start_frame = max(0, int(start * fps))
        end_frame = min(num_frames - 1, int(end * fps)) if num_frames > 0 else 0

        is_multikill = False
        if num_frames > 0:
            for f in range(start_frame, end_frame + 1):
                if f < num_frames and multikill_mask[f]:
                    is_multikill = True
                    break

        category = ClipCategory.MULTIPLE_KILLS if is_multikill else ClipCategory.SINGLE_KILL
        categorized.append(CategorizedClip(start=start, end=end, category=category))

    return categorized


def filter_clips_by_category(
    clips: List[CategorizedClip],
    enabled_categories: Optional[Set[ClipCategory]] = None,
) -> List[CategorizedClip]:
    """Keep only clips whose category is in *enabled_categories*.

    If *enabled_categories* is ``None``, all clips are returned (no filtering).
    """
    if enabled_categories is None:
        return clips
    return [c for c in clips if c.category in enabled_categories]
