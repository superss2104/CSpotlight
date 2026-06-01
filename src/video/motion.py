import cv2
import numpy as np
import subprocess
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VIDEO_PATH = BASE_DIR / "videos" / "video.mp4"

def detect_highlights(video_path):
    cap = cv2.VideoCapture(video_path) #used to capture the frames of a vid.
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video file: {video_path}")

    prev_blurred = None
    motion_scores = []
    while True:
        ret, frame = cap.read() #ret is a boolean and frame is a numpy 3d array which stores (height, width, channels(colors like BGR, not RGB, each value lies between 0 and 255))

        if not ret: break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) #convert to grayscale
        edges = cv2.Canny(gray, 50, 150) # Detect edges by finding sharp intensity changes; gradients >150 are strong edges,
# while gradients between 50-150 are kept only if connected to strong edges.
        current_blurred = cv2.GaussianBlur(edges, (9, 9), 0) #ksize is used to determine the window dimension to blur and sigmaX controls the influence of the surrounding pixels.
        if prev_blurred is not None:
            diff = cv2.absdiff(current_blurred, prev_blurred)
            # Convert the difference image to binary: pixels >25 become 255 (white),
            # highlighting significant changes between frames while ignoring small noise.
            _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)


            h, w = thresh.shape
            GRID_H, GRID_W = 4, 4
            cell_h = h // GRID_H
            cell_w = w // GRID_W

            cell_scores = []
            for i in range(GRID_H):
                for j in range(GRID_W):
                    cell = thresh[
                        i * cell_h:(i + 1) * cell_h,
                        j * cell_w:(j + 1) * cell_w
                    ]  #extracts the pixels by specifying row and column range to extract from.
                    cell_scores.append(cell.mean())

            motion_score = max(cell_scores) #The reason for taking max instead of mean is to make sure motion differences in
            #a small region isn't missed as averaging it out will dilute it.

            motion_scores.append(motion_score)
        prev_blurred = current_blurred

    fps = cap.get(cv2.CAP_PROP_FPS)
    window_size = int(fps * 1)
    windows = sliding_windows(motion_scores,window_size,10)
    highlight_windows = percentile_threshold(windows)
    merged = merge_windows(highlight_windows)

    MIN_EVENT_DURATION = 1.2
    filtered = []
    for start_frame, end_frame in merged:
        duration = (end_frame - start_frame) / fps
        if duration >= MIN_EVENT_DURATION:
            filtered.append((start_frame, end_frame))
    merged = filtered

    timestamps = frames_to_timestamps(merged, fps)
    timestamps = suppress_overlapping_clips(timestamps)
    cap.release()
    cv2.destroyAllWindows()

    return timestamps



def percentile_threshold(windows, percentile = 65):
    if not windows:
        return []
    scores = [w[2] for w in windows]
    threshold = np.percentile(scores, percentile)

    highlight_windows = [
        w for w in windows if w[2] >= threshold
    ]
    print(len(highlight_windows), "highlight windows")
    return highlight_windows


def sliding_windows(motion_scores, window_size, step_size):
    windows = []
    i = 0

    while i + window_size <= len(motion_scores):
        window = motion_scores[i : i + window_size]
        window_score = sum(window) / len(window)

        windows.append((i, i + window_size - 1, window_score))
        i += step_size
        # Ensure the last frame is included in a full-sized window
    if len(motion_scores) >= window_size:
        last_start = len(motion_scores) - window_size

        if not windows or windows[-1][0] != last_start:
            window = motion_scores[last_start:]
            window_score = sum(window) / len(window)

            windows.append(
                (last_start, len(motion_scores) - 1, window_score)
            )
    return windows

def merge_windows(windows):
    if not windows:
        return []
    merged = []
    current_start, current_end = windows[0][:2] #tuple unpacking. 0 is the index and :2 slices upto the
    # second index only so that only the first two values are taken into consideration during assignment
   

    for i in windows[1:]:
        next_start, next_end = i[:2]
        if next_start <= current_end:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    merged.append((current_start, current_end))
    return merged

def frames_to_timestamps(merged_windows, fps, clip_len=6.0):
    timestamps = []
    START_BIAS = 0.5
    half = clip_len / 2

    for start_frame, end_frame in merged_windows:
        center = (start_frame + end_frame) // 2
        start_time = max(0, center / fps - half + START_BIAS)
        end_time = center / fps + half
        timestamps.append((start_time, end_time))

    return timestamps


def cut_clips(video_path, timestamps, output_dir="clips"):
    os.makedirs(output_dir, exist_ok=True)

    for idx, (start, end) in enumerate(timestamps):
        output_path = os.path.join(output_dir, f"clip_{idx+1}.mp4")

        command = [
            "ffmpeg",
            "-ss", str(start),
            "-to", str(end),
            "-i", video_path,
            "-c", "copy",
            output_path,
            "-y"  # overwrite if exists
        ]

        subprocess.run(command, check=True)

def suppress_overlapping_clips(timestamps, min_gap=1.0):
    if not timestamps:
        return []

    timestamps.sort()
    filtered = [timestamps[0]]

    for start, end in timestamps[1:]:
        last_start, last_end = filtered[-1]

        if start <= last_end - min_gap: #Makes sure that if the next clip starts too
            # close to the previous one tghen it is ignored
            continue
        filtered.append((start, end))

    return filtered




if __name__ == "__main__":
    video = "./videos/video.mp4"
    timestamps = detect_highlights(str(VIDEO_PATH))
    cut_clips(str(VIDEO_PATH), timestamps)
