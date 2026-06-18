import logging

import cv2

try:
    from .clips import cut_clips
except ImportError:  # Support running src/main.py directly.
    from video.clips import cut_clips

LOGGER = logging.getLogger(__name__)


def extract_motion_scores(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video file: {video_path}")

    try:
        prev_blurred = None
        motion_scores = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            current_blurred = cv2.GaussianBlur(edges, (9, 9), 0)

            if prev_blurred is not None:
                diff = cv2.absdiff(current_blurred, prev_blurred)
                _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

                h, w = thresh.shape
                grid_h, grid_w = 4, 4
                cell_h = h // grid_h
                cell_w = w // grid_w

                cell_scores = []
                for i in range(grid_h):
                    for j in range(grid_w):
                        cell = thresh[
                            i * cell_h : (i + 1) * cell_h,
                            j * cell_w : (j + 1) * cell_w,
                        ]
                        cell_scores.append(cell.mean()) #append the mean value of each grid

                motion_scores.append(max(cell_scores)) #take the maxm value among all such mean values 
            else:
                motion_scores.append(0.0)

            prev_blurred = current_blurred

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            LOGGER.warning("Invalid FPS metadata (%s) for %s. Falling back to 30 FPS.", fps, video_path)
            fps = 30.0

        return motion_scores, fps
    finally:
        cap.release()
        cv2.destroyAllWindows()


def detect_highlights(video_path, motion_weight=None, audio_weight=None, killfeed_weight=None):
    try:
        from ..highlight.pipeline import detect_highlights as pipeline_detect_highlights
    except ImportError:  # Support running src/main.py directly.
        from highlight.pipeline import detect_highlights as pipeline_detect_highlights

    return pipeline_detect_highlights(
        video_path,
        motion_weight=motion_weight,
        audio_weight=audio_weight,
        killfeed_weight=killfeed_weight,
    )
