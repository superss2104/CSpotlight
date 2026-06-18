import unittest
from unittest.mock import patch

from src.highlight.pipeline import build_highlight_scores
from src.highlight.scoring import combine_multiple_scores


class PipelineScoringTests(unittest.TestCase):
    @patch("src.highlight.pipeline.extract_audio_scores")
    @patch("src.highlight.pipeline.extract_killfeed_scores")
    def test_build_highlight_scores_uses_runtime_weights(self, mock_killfeed, mock_extract_audio_scores):
        mock_extract_audio_scores.return_value = [0, 10, 0]
        mock_killfeed.return_value = []

        scores = build_highlight_scores(
            "video.mp4",
            [0, 0, 0],
            fps=30.0,
            motion_weight=0.0,
            audio_weight=1.0,
            killfeed_weight=0.0,
        )

        self.assertEqual(scores, [0.0, 1.0, 0.0])

    @patch("src.highlight.pipeline.extract_audio_scores")
    @patch("src.highlight.pipeline.extract_killfeed_scores")
    def test_build_highlight_scores_falls_back_to_motion_only(self, mock_killfeed, mock_extract_audio_scores):
        mock_extract_audio_scores.return_value = []
        mock_killfeed.return_value = []

        scores = build_highlight_scores("video.mp4", [1, 2, 3], fps=30.0)

        self.assertEqual(scores, [1, 2, 3])



class CombineMultipleScoresTests(unittest.TestCase):
    def test_three_signals(self):
        motion = [0, 10, 0]
        audio = [0, 0, 10]
        killfeed = [10, 0, 0]
        weights = [0.45, 0.30, 0.25]

        combined = combine_multiple_scores([motion, audio, killfeed], weights)

        self.assertEqual(len(combined), 3)
        # Frame 0: motion=0, audio=0, killfeed=1.0 → 0.25
        self.assertAlmostEqual(combined[0], 0.25)
        # Frame 1: motion=1, audio=0, killfeed=0 → 0.45
        self.assertAlmostEqual(combined[1], 0.45)
        # Frame 2: motion=0, audio=1, killfeed=0 → 0.30
        self.assertAlmostEqual(combined[2], 0.30)

    def test_mismatched_lengths_raises(self):
        with self.assertRaises(ValueError):
            combine_multiple_scores([[1, 2], [3, 4]], [0.5])

    def test_empty_primary_returns_empty(self):
        result = combine_multiple_scores([[], [1, 2]], [0.5, 0.5])
        self.assertEqual(result, [])

