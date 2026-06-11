import unittest

from src.highlight.timestamps import suppress_overlapping_clips_by_score
from src.video.motion import merge_windows, sliding_windows, suppress_overlapping_clips


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

    def test_suppress_overlapping_clips_keeps_well_spaced(self):
        timestamps = [(0.0, 3.0), (2.2, 4.0), (5.2, 7.0)]
        filtered = suppress_overlapping_clips(timestamps, min_gap=1.0)
        self.assertEqual(filtered, [(0.0, 3.0), (5.2, 7.0)])

    def test_suppress_overlapping_clips_by_score_keeps_stronger_clip(self):
        # Clips (0,5) and (4,9) overlap by only 1s out of 5s (20%), which is
        # under the 50% threshold, so all three distinct clips are kept.
        timestamps = [(0.0, 5.0), (4.0, 9.0), (12.0, 16.0)]
        scores = [0.25, 0.9, 0.5]

        filtered = suppress_overlapping_clips_by_score(timestamps, scores, min_gap=0.75)

        self.assertEqual(filtered, [(0.0, 5.0), (4.0, 9.0), (12.0, 16.0)])


if __name__ == "__main__":
    unittest.main()
