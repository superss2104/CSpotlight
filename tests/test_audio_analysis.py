import unittest

import numpy as np

from src.audio.analysis import audio_samples_to_frame_scores


class AudioAnalysisTests(unittest.TestCase):
    def test_audio_samples_to_frame_scores_matches_target_length(self):
        samples = np.ones(16000, dtype=np.float32) * 0.5
        scores = audio_samples_to_frame_scores(samples, fps=10, target_length=10, sample_rate=16000)
        self.assertEqual(len(scores), 10)

    def test_audio_samples_to_frame_scores_handles_empty_samples(self):
        scores = audio_samples_to_frame_scores(np.array([], dtype=np.float32), fps=10, target_length=10)
        self.assertEqual(scores, [])

    def test_audio_samples_to_frame_scores_detects_louder_frame(self):
        samples = np.zeros(16000, dtype=np.float32)
        samples[8000:9600] = 1.0
        scores = audio_samples_to_frame_scores(samples, fps=10, target_length=10, sample_rate=16000)
        self.assertGreater(scores[5], scores[4])


if __name__ == "__main__":
    unittest.main()
