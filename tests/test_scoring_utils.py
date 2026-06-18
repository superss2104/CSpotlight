import unittest

from src.highlight.scoring import combine_multiple_scores, normalize_scores


class ScoringUtilsTests(unittest.TestCase):
    def test_normalize_scores_scales_values(self):
        self.assertEqual(normalize_scores([2, 4, 6]), [0.0, 0.5, 1.0])

    def test_normalize_scores_handles_constant_values(self):
        self.assertEqual(normalize_scores([3, 3, 3]), [0.0, 0.0, 0.0])

    def test_combine_multiple_scores_preserves_primary_length(self):
        combined = combine_multiple_scores([[0, 10, 20], [5]], [0.5, 0.5])
        self.assertEqual(len(combined), 3)

    def test_combine_multiple_scores_uses_secondary_signal(self):
        combined = combine_multiple_scores([[0, 0, 0], [0, 10, 0]], [0.5, 0.5])
        self.assertEqual(combined, [0.0, 0.5, 0.0])


if __name__ == "__main__":
    unittest.main()
