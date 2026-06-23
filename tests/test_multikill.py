import unittest

from src.cs2.multikill import (
    MultikillEvent,
    build_multikill_mask,
    detect_multikill_events,
)


# ---------------------------------------------------------------------------
# Helper: simulate a realistic killfeed signal.
# ---------------------------------------------------------------------------
# In a real video, a killfeed entry appears (count rises) and persists for
# many frames before fading.  The rising-edge detector only counts the
# *increase* as a new kill — so we build test signals that model this.

def _make_signal(length, appearances):
    """Build a kill_counts signal with realistic persistence.

    *appearances* is a list of ``(appear_frame, persist_frames)`` tuples.
    Each appearance increases the active kill count by 1 at *appear_frame*
    and decreases it again after *persist_frames* frames.
    """
    signal = [0] * length
    for appear, persist in appearances:
        for f in range(appear, min(appear + persist, length)):
            signal[f] += 1
    return signal


class DetectMultikillEventsTests(unittest.TestCase):
    """Tests for detect_multikill_events()."""

    def test_empty_kill_counts(self):
        events = detect_multikill_events([], fps=30.0)
        self.assertEqual(events, [])

    def test_all_zeros_returns_no_events(self):
        kill_counts = [0] * 300
        events = detect_multikill_events(kill_counts, fps=30.0)
        self.assertEqual(events, [])

    def test_single_kill_persisting_is_not_multikill(self):
        """One kill visible for many frames should NOT be a multikill."""
        # Kill appears at frame 100, persists for 90 frames (~3s at 30fps).
        kill_counts = _make_signal(300, [(100, 90)])
        events = detect_multikill_events(kill_counts, fps=30.0)
        self.assertEqual(events, [])

    def test_two_kills_spread_far_apart_no_multikill(self):
        """Two kills separated by more than the time window are not a multikill."""
        # Kill at frame 30 (persists 60 frames), kill at frame 450 (persists 60).
        # Gap is ~14 seconds — well beyond 5s window.
        kill_counts = _make_signal(600, [(30, 60), (450, 60)])
        events = detect_multikill_events(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(events, [])

    def test_two_kills_within_window(self):
        """Two kills within the 5-second window produce one multikill event."""
        # Kill at frame 60 (persists 90 frames), kill at frame 120 (persists 90).
        # At frame 120, both are visible so count rises from 1→2.
        kill_counts = _make_signal(300, [(60, 90), (120, 90)])
        events = detect_multikill_events(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].total_kills, 2)
        self.assertEqual(events[0].start_frame, 60)
        self.assertEqual(events[0].end_frame, 120)

    def test_triple_kill_single_event(self):
        """Three rapid kills should produce one event with total_kills=3."""
        # Each kill persists 90 frames so they overlap — the count rises
        # at each new appearance: 0→1 at frame 30, 1→2 at frame 60, 2→3 at frame 90.
        kill_counts = _make_signal(300, [(30, 90), (60, 90), (90, 90)])
        events = detect_multikill_events(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].total_kills, 3)

    def test_two_separate_multikills(self):
        """Two clusters of kills far apart produce two events."""
        kill_counts = _make_signal(900, [
            # Cluster 1: frames 30 and 60
            (30, 60), (60, 60),
            # Cluster 2: frames 600 and 630  (20s+ later)
            (600, 60), (630, 60),
        ])
        events = detect_multikill_events(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].total_kills, 2)
        self.assertEqual(events[1].total_kills, 2)

    def test_simultaneous_two_outlines_is_multikill(self):
        """Two outlines appearing on the same frame (jump from 0→2) = multikill."""
        kill_counts = [0] * 100
        # Simulate two outlines appearing simultaneously at frame 50.
        for f in range(50, 80):
            kill_counts[f] = 2
        events = detect_multikill_events(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].total_kills, 2)
        self.assertEqual(events[0].start_frame, 50)
        self.assertEqual(events[0].end_frame, 50)

    def test_invalid_fps_returns_empty(self):
        events = detect_multikill_events([0, 1, 1, 0], fps=0.0)
        self.assertEqual(events, [])

    def test_custom_time_window(self):
        """A shorter window should miss kills that a longer window catches."""
        # Kill at frame 30 (1.0s), kill at frame 120 (4.0s). Gap = 3s.
        kill_counts = _make_signal(300, [(30, 30), (120, 30)])
        # With 2s window, they should NOT be a multikill.
        events_short = detect_multikill_events(kill_counts, fps=30.0, time_window=2.0)
        self.assertEqual(len(events_short), 0)
        # With 5s window, they SHOULD be.
        events_long = detect_multikill_events(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(len(events_long), 1)

    def test_single_kill_with_noisy_count_not_multikill(self):
        """A single kill whose count stays at 1 for many frames is NOT multi."""
        # Simulates what the user saw: AWP flick, one killfeed entry for ~3s.
        kill_counts = [0] * 200
        for f in range(50, 140):  # 3 seconds of visibility at 30fps
            kill_counts[f] = 1
        events = detect_multikill_events(kill_counts, fps=30.0)
        self.assertEqual(events, [])

    def test_flickering_single_kill_not_multikill(self):
        """A single kill whose outline flickers (1->0->1->0->1) is NOT multi.

        Reproduces the real-world bug: the killfeed detector is noisy and
        a single persistent outline can be detected intermittently, e.g.:
          frame 652: count=1, frame 653-666: count=0, frame 667-668: count=1,
          frame 669: count=0, frame 670-673: count=1.
        This produces 3 rising edges within 0.35 seconds — all from the
        same kill.  The debounce must suppress the duplicates.
        """
        # Exact pattern from the user's test video at 60fps.
        kill_counts = [0] * 826
        kill_counts[652] = 1
        # Gap of 14 frames (0.23s) — same kill flickering
        kill_counts[667] = 1
        kill_counts[668] = 1
        # Gap of 1 frame (0.017s) — same kill flickering
        kill_counts[670] = 1
        kill_counts[671] = 1
        kill_counts[672] = 1
        kill_counts[673] = 1
        events = detect_multikill_events(kill_counts, fps=60.0)
        self.assertEqual(events, [], "Flickering single kill should not be detected as multikill")


class BuildMultikillMaskTests(unittest.TestCase):
    """Tests for build_multikill_mask()."""

    def test_empty_input(self):
        mask = build_multikill_mask([], fps=30.0)
        self.assertEqual(mask, [])

    def test_no_kills_all_false(self):
        mask = build_multikill_mask([0] * 100, fps=30.0)
        self.assertEqual(len(mask), 100)
        self.assertTrue(all(not m for m in mask))

    def test_multikill_frames_marked_true(self):
        # Two kills: frame 50 and frame 80.
        kill_counts = _make_signal(200, [(50, 40), (80, 40)])
        mask = build_multikill_mask(kill_counts, fps=30.0, time_window=5.0)
        self.assertEqual(len(mask), 200)
        # Frames 50 and 80 (the appearance frames) should be True.
        self.assertTrue(mask[50])
        self.assertTrue(mask[80])
        for i in range(50, 81):
            self.assertTrue(mask[i], f"Frame {i} should be marked as multikill")
        # Frames outside the event should be False.
        self.assertFalse(mask[0])
        self.assertFalse(mask[49])
        self.assertFalse(mask[81])

    def test_single_kill_not_marked(self):
        kill_counts = _make_signal(200, [(100, 60)])
        mask = build_multikill_mask(kill_counts, fps=30.0)
        self.assertTrue(all(not m for m in mask))


if __name__ == "__main__":
    unittest.main()
