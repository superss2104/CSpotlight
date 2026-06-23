import unittest

import cv2
import numpy as np

from src.cs2.killfeed import (
    KillfeedConfig,
    _align_scores,
    _build_red_mask,
    detect_player_kills,
    find_red_outlines,
    is_hollow_rectangle,
)


def _make_blank_frame(width=1920, height=1080):
    """Create a blank dark frame simulating a game scene."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def _draw_red_outline(frame, x, y, w, h, thickness=2):
    """Draw a red rectangular outline on the frame (simulating a kill-feed entry).

    Uses the BGR color calibrated from the real CS2 screenshot: ~(36, 36, 158).
    """
    red_bgr = (36, 36, 200)
    cv2.rectangle(frame, (x, y), (x + w, y + h), red_bgr, thickness)
    return frame


class DetectPlayerKillsTests(unittest.TestCase):
    def test_blank_frame_returns_zero(self):
        frame = _make_blank_frame()
        score = detect_player_kills(frame)
        self.assertEqual(score, 0.0)

    def test_single_red_outline_scores_one(self):
        frame = _make_blank_frame()
        # Draw a red outline in the kill-feed ROI region (top-right)
        _draw_red_outline(frame, 1200, 30, 650, 35, thickness=2)
        score = detect_player_kills(frame)
        self.assertGreaterEqual(score, 1.0)

    def test_two_red_outlines_scores_higher(self):
        frame = _make_blank_frame()
        _draw_red_outline(frame, 1200, 30, 650, 35, thickness=2)
        _draw_red_outline(frame, 1200, 80, 650, 35, thickness=2)
        score = detect_player_kills(frame)
        self.assertGreater(score, 1.0)

    def test_solid_red_rectangle_is_rejected(self):
        frame = _make_blank_frame()
        # Draw a FILLED red rectangle — should be rejected by the hollow check.
        cv2.rectangle(frame, (1200, 30), (1850, 65), (36, 36, 200), -1)
        score = detect_player_kills(frame)
        self.assertEqual(score, 0.0)

    def test_red_outside_roi_is_ignored(self):
        frame = _make_blank_frame()
        # Draw red outline in the bottom-left corner (outside kill-feed ROI).
        _draw_red_outline(frame, 50, 900, 400, 35, thickness=2)
        score = detect_player_kills(frame)
        self.assertEqual(score, 0.0)

    def test_multi_kill_score_is_capped(self):
        config = KillfeedConfig(max_score=2.0)
        frame = _make_blank_frame()
        # Draw 5 outlines — score should be capped at config.max_score.
        for i in range(5):
            _draw_red_outline(frame, 1200, 20 + i * 45, 650, 35, thickness=2)
        score = detect_player_kills(frame, config=config)
        self.assertLessEqual(score, 2.0)


class AlignScoresTests(unittest.TestCase):
    def test_same_length(self):
        scores = [1.0, 2.0, 3.0]
        self.assertEqual(_align_scores(scores, 3), scores)

    def test_shorter_input(self):
        scores = [1.0, 3.0]
        aligned = _align_scores(scores, 4)
        self.assertEqual(len(aligned), 4)

    def test_longer_input(self):
        scores = [1.0, 2.0, 3.0, 4.0, 5.0]
        aligned = _align_scores(scores, 3)
        self.assertEqual(len(aligned), 3)

    def test_empty_input(self):
        aligned = _align_scores([], 5)
        self.assertEqual(aligned, [0.0] * 5)


class FindRedOutlinesTests(unittest.TestCase):
    def test_no_red_returns_empty(self):
        roi = np.zeros((200, 400, 3), dtype=np.uint8)
        roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red_mask = _build_red_mask(roi_hsv, KillfeedConfig())
        outlines = find_red_outlines(red_mask, roi_hsv, KillfeedConfig())
        self.assertEqual(outlines, [])

    def test_small_noise_is_rejected(self):
        roi = np.zeros((200, 400, 3), dtype=np.uint8)
        # Draw a tiny red dot — too small to be a kill-feed outline.
        cv2.circle(roi, (100, 100), 3, (36, 36, 200), 1)
        roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        red_mask = _build_red_mask(roi_hsv, KillfeedConfig())
        outlines = find_red_outlines(red_mask, roi_hsv, KillfeedConfig())
        self.assertEqual(outlines, [])


class HollowRectangleTests(unittest.TestCase):
    def test_hollow_rectangle_accepted(self):
        mask = np.zeros((200, 600), dtype=np.uint8)
        cv2.rectangle(mask, (10, 50), (580, 90), 255, 2)  # hollow
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.assertTrue(len(contours) > 0)
        accepted = is_hollow_rectangle(contours[0], mask, min_area=50, config=KillfeedConfig())
        self.assertTrue(accepted)

    def test_filled_rectangle_rejected(self):
        mask = np.zeros((200, 600), dtype=np.uint8)
        cv2.rectangle(mask, (10, 50), (580, 90), 255, -1)  # filled
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.assertTrue(len(contours) > 0)
        accepted = is_hollow_rectangle(contours[0], mask, min_area=50, config=KillfeedConfig())
        self.assertFalse(accepted)

    def test_death_fill_with_text_gaps_rejected(self):
        """Simulates a CS2 death entry: red fill with gaps from text/icons.

        The overall fill ratio is ~30-40% (text creates holes), which would
        have slipped past the old 0.4 threshold.  The new inner-fill check
        catches it because the interior (away from edges) still has
        substantial red fill.
        """
        mask = np.zeros((200, 600), dtype=np.uint8)
        # Start with a filled red rectangle (death entry background).
        cv2.rectangle(mask, (10, 50), (580, 90), 255, -1)
        # Cut out horizontal stripes to simulate text/weapon icons on top.
        # This brings the overall fill ratio down but the interior still
        # has significant red.
        mask[55:60, 50:200] = 0    # text region 1
        mask[65:70, 100:350] = 0   # text region 2
        mask[75:80, 200:500] = 0   # weapon icon region
        mask[58:72, 280:320] = 0   # another gap
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.assertTrue(len(contours) > 0)
        accepted = is_hollow_rectangle(contours[0], mask, min_area=50, config=KillfeedConfig())
        self.assertFalse(accepted, "Death fill with text gaps should be rejected by inner-fill check")

    def test_square_shape_rejected(self):
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(mask, (10, 10), (100, 100), 255, 2)  # square, aspect ~1:1
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.assertTrue(len(contours) > 0)
        accepted = is_hollow_rectangle(contours[0], mask, min_area=50, config=KillfeedConfig())
        self.assertFalse(accepted)


if __name__ == "__main__":
    unittest.main()
