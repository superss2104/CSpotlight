import unittest

from src.highlight.timestamps import merge_overlapping_clips
from src.highlight.windows import merge_windows, sliding_windows


class MotionUtilsTests(unittest.TestCase):
    def test_sliding_windows_adds_tail_window(self):
        scores = [1, 2, 3, 4, 5]
        windows = sliding_windows(scores, window_size=3, step_size=2)
        self.assertEqual(windows, [(0, 2, 2.0), (2, 4, 4.0)])

    def test_merge_windows_merges_overlaps(self):
        windows = [(0, 10, 1.0), (8, 15, 2.0), (20, 25, 0.5)]
        merged = merge_windows(windows)
        self.assertEqual(merged, [(0, 15), (20, 25)])

    def test_merge_windows_merges_small_gaps_when_allowed(self):
        windows = [(0, 10, 1.0), (14, 20, 2.0)]
        merged = merge_windows(windows, max_gap=5)
        self.assertEqual(merged, [(0, 20)])

    def test_merge_overlapping_clips_merges_overlaps(self):
        timestamps = [(0.0, 5.0), (4.0, 9.0), (12.0, 16.0)]
        merged = merge_overlapping_clips(timestamps, min_gap=0.75)
        self.assertEqual(merged, [(0.0, 9.0), (12.0, 16.0)])


if __name__ == "__main__":
    unittest.main()
