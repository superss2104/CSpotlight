import unittest

from src.highlight.categories import (
    CategorizedClip,
    ClipCategory,
    categorize_clips,
    filter_clips_by_category,
)


class CategorizedClipTests(unittest.TestCase):
    """Tests for CategorizedClip backwards-compatibility features."""

    def test_tuple_unpacking(self):
        clip = CategorizedClip(start=1.0, end=5.0, category=ClipCategory.SINGLE_KILL)
        start, end = clip
        self.assertEqual(start, 1.0)
        self.assertEqual(end, 5.0)

    def test_indexed_access(self):
        clip = CategorizedClip(start=2.0, end=8.0, category=ClipCategory.MULTIPLE_KILLS)
        self.assertEqual(clip[0], 2.0)
        self.assertEqual(clip[1], 8.0)

    def test_len(self):
        clip = CategorizedClip(start=0.0, end=1.0, category=ClipCategory.SINGLE_KILL)
        self.assertEqual(len(clip), 2)

    def test_iteration_in_loop(self):
        """Simulates the pattern: for start, end in clips."""
        clips = [
            CategorizedClip(1.0, 3.0, ClipCategory.SINGLE_KILL),
            CategorizedClip(5.0, 9.0, ClipCategory.MULTIPLE_KILLS),
        ]
        results = []
        for start, end in clips:
            results.append((start, end))
        self.assertEqual(results, [(1.0, 3.0), (5.0, 9.0)])


class CategorizeClipsTests(unittest.TestCase):
    """Tests for categorize_clips()."""

    def test_empty_timestamps(self):
        result = categorize_clips([], [], fps=30.0)
        self.assertEqual(result, [])

    def test_clip_overlapping_multikill_is_multiple_kills(self):
        timestamps = [(1.0, 5.0)]
        # 150 frames at 30fps = 5 seconds. Mark frames 30-90 as multikill.
        mask = [False] * 150
        for i in range(30, 91):
            mask[i] = True
        result = categorize_clips(timestamps, mask, fps=30.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].category, ClipCategory.MULTIPLE_KILLS)

    def test_clip_not_overlapping_multikill_is_single_kill(self):
        timestamps = [(0.0, 0.5)]
        # Multikill frames are at 4-5 seconds — clip is at 0-0.5s
        mask = [False] * 150
        for i in range(120, 150):
            mask[i] = True
        result = categorize_clips(timestamps, mask, fps=30.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].category, ClipCategory.SINGLE_KILL)

    def test_multiple_clips_mixed_categories(self):
        timestamps = [(0.0, 1.0), (3.0, 5.0)]
        mask = [False] * 150
        # Mark frames 90-120 (3s-4s) as multikill
        for i in range(90, 121):
            mask[i] = True
        result = categorize_clips(timestamps, mask, fps=30.0)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].category, ClipCategory.SINGLE_KILL)
        self.assertEqual(result[1].category, ClipCategory.MULTIPLE_KILLS)

    def test_empty_mask_all_single_kills(self):
        timestamps = [(1.0, 3.0), (5.0, 7.0)]
        mask = []  # No killfeed data at all
        result = categorize_clips(timestamps, mask, fps=30.0)
        self.assertEqual(len(result), 2)
        for clip in result:
            self.assertEqual(clip.category, ClipCategory.SINGLE_KILL)


class FilterClipsByCategoryTests(unittest.TestCase):
    """Tests for filter_clips_by_category()."""

    def test_none_keeps_all(self):
        clips = [
            CategorizedClip(0.0, 1.0, ClipCategory.SINGLE_KILL),
            CategorizedClip(2.0, 3.0, ClipCategory.MULTIPLE_KILLS),
        ]
        result = filter_clips_by_category(clips, enabled_categories=None)
        self.assertEqual(len(result), 2)

    def test_filter_single_kills_only(self):
        clips = [
            CategorizedClip(0.0, 1.0, ClipCategory.SINGLE_KILL),
            CategorizedClip(2.0, 3.0, ClipCategory.MULTIPLE_KILLS),
            CategorizedClip(4.0, 5.0, ClipCategory.SINGLE_KILL),
        ]
        result = filter_clips_by_category(clips, {ClipCategory.SINGLE_KILL})
        self.assertEqual(len(result), 2)
        self.assertTrue(all(c.category == ClipCategory.SINGLE_KILL for c in result))

    def test_filter_multi_kills_only(self):
        clips = [
            CategorizedClip(0.0, 1.0, ClipCategory.SINGLE_KILL),
            CategorizedClip(2.0, 3.0, ClipCategory.MULTIPLE_KILLS),
        ]
        result = filter_clips_by_category(clips, {ClipCategory.MULTIPLE_KILLS})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].category, ClipCategory.MULTIPLE_KILLS)

    def test_empty_enabled_set_keeps_nothing(self):
        clips = [
            CategorizedClip(0.0, 1.0, ClipCategory.SINGLE_KILL),
            CategorizedClip(2.0, 3.0, ClipCategory.MULTIPLE_KILLS),
        ]
        result = filter_clips_by_category(clips, set())
        self.assertEqual(len(result), 0)

    def test_all_categories_enabled_keeps_all(self):
        clips = [
            CategorizedClip(0.0, 1.0, ClipCategory.SINGLE_KILL),
            CategorizedClip(2.0, 3.0, ClipCategory.MULTIPLE_KILLS),
        ]
        result = filter_clips_by_category(clips, {ClipCategory.SINGLE_KILL, ClipCategory.MULTIPLE_KILLS})
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
