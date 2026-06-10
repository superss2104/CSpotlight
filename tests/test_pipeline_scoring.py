import unittest
from unittest.mock import patch

from src.highlight.pipeline import build_highlight_scores, score_events


class PipelineScoringTests(unittest.TestCase):
    @patch("src.highlight.pipeline.extract_audio_scores")
    def test_build_highlight_scores_uses_runtime_weights(self, mock_extract_audio_scores):
        mock_extract_audio_scores.return_value = [0, 10, 0]

        scores = build_highlight_scores(
            "video.mp4",
            [0, 0, 0],
            fps=30.0,
            motion_weight=0.0,
            audio_weight=1.0,
        )

        self.assertEqual(scores, [0.0, 1.0, 0.0])

    @patch("src.highlight.pipeline.extract_audio_scores")
    def test_build_highlight_scores_falls_back_to_motion_only(self, mock_extract_audio_scores):
        mock_extract_audio_scores.return_value = []

        scores = build_highlight_scores("video.mp4", [1, 2, 3], fps=30.0)

        self.assertEqual(scores, [1, 2, 3])

    def test_score_events_uses_strongest_overlapping_window(self):
        events = [(0, 20), (40, 60)]
        scored_windows = [(0, 10, 0.25), (8, 18, 0.8), (45, 55, 0.6)]

        scores = score_events(events, scored_windows)

        self.assertEqual(scores, [0.8, 0.6])


if __name__ == "__main__":
    unittest.main()
