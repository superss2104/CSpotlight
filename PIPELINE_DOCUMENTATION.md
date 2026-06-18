# CSpotlight Pipeline Documentation

This document describes the current end-to-end pipeline implemented in the repository, starting from video loading and ending with generated clip files.

The codebase is currently a small prototype centered around one processing path:

1. Load a single input video.
2. Scan it frame by frame.
3. Compute a motion score for each frame transition.
4. Extract audio loudness scores from the same video.
5. Extract kill-feed occurrences using shape detection in the top right corner.
6. Fuse motion, audio, and kill-feed scores, and apply kill-feed gating.
7. Aggregate fused scores into candidate highlight windows.
8. Convert those windows into timestamps.
9. Cut clips with FFmpeg.

## 1. Entry Point

The application starts in [`src/main.py`](src/main.py).

### Main responsibilities

- Parse command-line arguments.
- Resolve the default input video path.
- Validate that the input file exists.
- Run highlight detection.
- Cut clips from the detected timestamps.

### Default paths

`src/main.py` uses these defaults:

- Input: `data/videos/video.mp4`
- Legacy fallback: `src/video/videos/video.mp4`
- Output: `clips/`

The default input path is resolved by `resolve_default_video()`. If `data/videos/video.mp4` exists, it is used. Otherwise the code falls back to the legacy path.

### Score weight options

The CLI also accepts runtime score weights:

```bash
python src/main.py --motion-weight 0.25 --audio-weight 0.25 --killfeed-weight 0.50
```

If these options are omitted, the constants in [`src/highlight/pipeline.py`](src/highlight/pipeline.py) are used.

## 2. Runtime Flow

The pipeline executed by `main()` is:

1. Parse arguments.
2. Resolve `video_path` and `output_dir`.
3. Raise an error if the input file does not exist.
4. Call `detect_highlights(video_path)`.
5. Receive a list of `(start_time, end_time)` timestamps.
6. Pass those timestamps to `cut_clips(video_path, timestamps, output_dir)`.

Logging is initialized only when the file is run as a script, not when imported as a module.

## 3. Modular Structure

The pipeline is split by responsibility so future signals, such as audio analysis, can be added without changing clip generation or timestamp utilities.

- [`src/highlight/pipeline.py`](src/highlight/pipeline.py): end-to-end highlight detection orchestration
- [`src/audio/analysis.py`](src/audio/analysis.py): audio extraction and frame-aligned audio scoring
- [`src/cs2/killfeed.py`](src/cs2/killfeed.py): CS2 kill-feed detection using red-outline shape analysis
- [`src/video/motion.py`](src/video/motion.py): visual motion score extraction
- [`src/video/clips.py`](src/video/clips.py): FFmpeg clip extraction
- [`src/highlight/windows.py`](src/highlight/windows.py): sliding windows, percentile filtering, merging, and duration filtering
- [`src/highlight/timestamps.py`](src/highlight/timestamps.py): frame-range to timestamp conversion and clip overlap suppression
- [`src/highlight/scoring.py`](src/highlight/scoring.py): score normalization and multi-signal score fusion

`src/video/motion.py` keeps compatibility exports for the previous API, so existing imports of `detect_highlights()`, `cut_clips()`, and the window/timestamp helpers continue to work.

## 4. Video Loading

The first real processing step happens in `extract_motion_scores()` in [`src/video/motion.py`](src/video/motion.py).

### Video capture

`extract_motion_scores(video_path)` opens the file with `cv2.VideoCapture(video_path)`.

- If OpenCV cannot open the file, the function raises `RuntimeError`.
- The frame loop then reads the video sequentially until `cap.read()` returns `False`.

This implementation does not write extracted frames to disk. Frames are decoded and processed in memory only.

## 5. Frame-by-Frame Motion Analysis

For every frame read from the video, the pipeline applies the following transformations:

### 4.1 Convert to grayscale

The frame is converted from BGR to grayscale with:

```python
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
```

This reduces the data to a single intensity channel.

### 4.2 Edge detection

Edges are extracted using Canny edge detection:

```python
edges = cv2.Canny(gray, 50, 150)
```

The thresholds used are:

- Lower threshold: `50`
- Upper threshold: `150`

This emphasizes structural changes rather than raw color changes.

### 4.3 Blur the edge map

The edge map is smoothed with a Gaussian blur:

```python
current_blurred = cv2.GaussianBlur(edges, (9, 9), 0)
```

The blur reduces noise and makes the motion signal less sensitive to tiny edge fluctuations.

### 4.4 Compare with the previous frame

Starting from the second frame, the current blurred edge map is compared with the previous blurred edge map:

```python
diff = cv2.absdiff(current_blurred, prev_blurred)
_, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
```

This creates a binary mask of changed pixels.

Threshold parameters:

- Difference threshold: `25`
- Binary output max value: `255`

### 4.5 Grid-based scoring

The threshold mask is divided into a `4 x 4` grid.

For each cell:

- The cell region is sliced from the mask.
- The mean value of that cell is computed.

The frame transition score is the maximum mean across all 16 cells.

This means the pipeline is biased toward the strongest local motion region in the frame rather than averaging the whole image.

### 4.6 Motion score list

Each processed frame transition contributes one entry to `motion_scores`.

Important detail:

- The first frame does not produce a score because there is no previous frame to compare against.
- If the video has `N` frames, the motion list will contain roughly `N - 1` scores.

## 6. FPS Handling

After frame scanning finishes, the code reads the video FPS metadata:

```python
fps = cap.get(cv2.CAP_PROP_FPS)
```

If the FPS value is missing, zero, or invalid, the code logs a warning and falls back to `30.0`.

This fallback matters because several later calculations depend on FPS:

- window size in frames
- minimum event duration
- timestamp conversion

## 7. Audio Analysis

After motion scores are extracted, [`src/highlight/pipeline.py`](src/highlight/pipeline.py) calls `extract_audio_scores()` from [`src/audio/analysis.py`](src/audio/analysis.py).

### 7.1 FFmpeg audio decoding

Audio is decoded with FFmpeg into raw mono PCM:

- video is ignored with `-vn`
- audio is converted to one channel with `-ac 1`
- audio is resampled to `16000 Hz`
- output format is signed 16-bit little-endian PCM
- decoded bytes are read from stdout, not written to disk

The audio module first looks for the bundled executable at `ffmpeg/bin/ffmpeg.exe`. If that file is missing, it falls back to `ffmpeg` on the system path.

### 7.2 Frame-aligned audio scoring

Decoded samples are split into chunks aligned to the motion score count. For each target video-frame score, the audio module computes:

- RMS loudness
- peak amplitude
- positive loudness onset compared with the previous chunk

The current audio score formula is:

```python
(0.40 * rms) + (0.30 * peak) + (0.30 * onset)
```

This keeps sustained loudness as the dominant signal while still giving some weight to spikes and sudden increases.

### 7.3 Safe fallback

If FFmpeg is missing, the video has no audio, audio extraction fails, or audio analysis raises an unexpected exception, the pipeline logs the issue and falls back to motion-only scoring. This preserves the existing pipeline behavior instead of failing highlight detection.

## 8. Kill-feed Analysis

After audio analysis, [`src/highlight/pipeline.py`](src/highlight/pipeline.py) calls `extract_killfeed_scores()` from [`src/cs2/killfeed.py`](src/cs2/killfeed.py).

### 8.1 Region of Interest (ROI)

The kill-feed in CS2 appears in the top right corner. The pipeline crops this region:

- X bounds: `60%` to `99%` of the width
- Y bounds: `1%` to `25%` of the height

### 8.2 Red Outline Detection

When a player gets a kill, their name in the kill-feed is outlined in red. The pipeline:
- Converts the ROI to HSV color space.
- Masks red pixels.
- Finds contours and checks if they form a hollow rectangle with an aspect ratio of at least `3.0`.
- Ensures the interior fill of the rectangle is low (to exclude solid red UI elements).

### 8.3 Scoring

If valid red rectangles are found, the frame is scored based on the count:
- First kill: `1.0`
- Additional kills: `+0.5` each
- Cap: `3.0` maximum score

Like audio, kill-feed analysis has a safe fallback and returns an empty list if it fails.

## 9. Score Fusion

Motion, audio, and kill-feed scores are combined in [`src/highlight/scoring.py`](src/highlight/scoring.py).

All signals are normalized to the `0.0` to `1.0` range before fusion. The current default weights are:

- Motion: `0.25`
- Audio: `0.25`
- Killfeed: `0.5`

The fused score formula is:

```python
combined = 0.25 * normalized_motion + 0.25 * normalized_audio + 0.5 * normalized_killfeed
```

### 9.1 Kill-feed Gate

After the basic score fusion, the pipeline enforces a logical gate: any frame where the kill-feed signal is exactly `0.0` has its combined score forcefully set to `0.0`. This ensures that high motion or audio (such as scoping in with a loud noise) cannot generate a highlight unless a kill-feed entry is also present.

The output score list keeps the motion score length so downstream windowing and timestamp conversion continue to operate on the same frame-based timeline.

Important practical detail: changing weights may change internal score windows without visibly changing the final output clips. After score fusion, the pipeline still applies percentile thresholding, window merging, 8-second timestamp centering, and overlap suppression. Nearby detections can therefore collapse into the same final clip even when the underlying score stream changed.

## 10. Candidate Highlight Window Detection

Once the final highlight score stream is built, [`src/highlight/pipeline.py`](src/highlight/pipeline.py) identifies likely highlight intervals in several stages.

### 10.1 Sliding windows

`window_size` is set to approximately one second of footage:

```python
window_size = max(1, int(round(fps)))
```

The window slides over the score list with a step size of `10` frames:

```python
windows = sliding_windows(motion_scores, window_size, 10)
```

Each window is stored as:

```python
(start_frame, end_frame, mean_score)
```

The helper lives in [`src/highlight/windows.py`](src/highlight/windows.py) and also adds a final tail window if the last chunk of the score list was not covered by the regular stepping logic.

### 10.2 Percentile thresholding

The window scores are filtered using the 50th percentile:

```python
highlight_windows = percentile_threshold(windows, percentile=50)
```

The threshold is computed with `np.percentile(scores, 50)`.

Any window whose score is greater than or equal to the percentile threshold is kept.

This is a relative thresholding strategy:

- It does not use a fixed hardcoded score cut-off.
- It adapts to the motion distribution of the specific video.

### 10.3 Merge overlapping windows

The selected windows are merged with `merge_windows()`.

Behavior:

- Windows are assumed to be in chronological order.
- If the next window starts before or at the current end, or within a small configurable gap, they are merged into one interval.
- Otherwise, the current interval is finalized and a new one begins.

This step collapses contiguous highlight-like regions into larger spans.

## 11. Duration Filtering

After merging, the code filters out short events:

```python
min_event_duration = 0.1
```

For each merged frame range:

```python
duration = (end_frame - start_frame) / fps
```

Only intervals with duration greater than or equal to `0.1` seconds are kept.

This removes brief spikes that are likely too small to be meaningful highlights.

## 12. Event Expansion

Before converting to timestamps, the pipeline applies `_expand_events_with_motion()` in [`src/highlight/pipeline.py`](src/highlight/pipeline.py).
Because the kill-feed is a lagging indicator (it appears *after* the kill), relying solely on it can clip the beginning of an engagement.

### Behavior
- The function scans the raw motion scores backward from each event in 0.5-second chunks.
- As long as a chunk's average motion score exceeds a threshold (0.15), the event's start is extended backward.
- This adaptively captures the aiming and repositioning before the kill.
- A fixed 2.0-second padding of calm footage is added before the detected onset.

## 13. Frame Ranges to Clip Timestamps

The expanded frame ranges are converted to time ranges by `frames_to_timestamps()` in [`src/highlight/timestamps.py`](src/highlight/timestamps.py).

### 13.1 Dynamic clip length

The pipeline handles short and long events differently:
- **Short events** (duration <= `DEFAULT_CLIP_LEN_SECONDS` [8.0s]): Receive a fixed 8-second clip length.
- **Long events**: The clip is continuous and spans the entire event duration, plus a small 2.0-second buffer at the end to avoid sudden cut-offs.

### 13.2 Start bias

A negative `start_bias` (default `-4.0` seconds) is applied to the clip start to include lead-in time before the event.

```python
clip_start = max(0, event_start + start_bias)
```

The start time is clamped to `0` so the clip never begins before the video start.

## 14. Clip Merging

The timestamp list is passed through `merge_overlapping_clips()`.

### Behavior

- The timestamps are sorted.
- The first timestamp is initialized as a merged clip.
- Each later timestamp is checked against the end of the last merged clip.
- If the new start is less than or equal to `last_end + min_gap` (default 0.75s), the clips are merged into one continuous clip.
- Otherwise, it is added as a new standalone clip.

This prevents overlapping clips from being exported redundantly and smoothly combines back-to-back action.

## 15. Clip Extraction

Final clip cutting happens in `cut_clips()` in [`src/video/clips.py`](src/video/clips.py).

### Output directory creation

The output folder is created if needed:

```python
os.makedirs(output_dir, exist_ok=True)
```

### FFmpeg invocation

For each timestamp pair, the code runs:

```bash
ffmpeg -ss <start> -to <end> -i <video_path> -c copy <output_path> -y
```

Key points:

- `-ss` and `-to` define the time slice.
- `-c copy` copies streams without re-encoding.
- `-y` overwrites existing files.

Output naming:

- `clip_1.mp4`
- `clip_2.mp4`
- and so on

### Practical implication

Because the pipeline uses stream copy, clip extraction is fast, but cut accuracy can depend on the source file structure and keyframe alignment.

After all clips are saved, `src/main.py` triggers a system notification sound (`winsound.MessageBeep`) to alert the user that processing is complete.

## 16. Test Coverage

The current tests live in [`tests/test_motion_utils.py`](tests/test_motion_utils.py).

They cover pure utility functions exposed through the compatibility layer in [`src/video/motion.py`](src/video/motion.py), plus audio and scoring helpers:

1. `sliding_windows()` adds the tail window correctly.
2. `merge_windows()` merges overlapping frame ranges.
3. `merge_overlapping_clips()` correctly combines clips that overlap or fall within the minimum gap.
4. `normalize_scores()` scales and handles constant values.
5. `combine_multiple_scores()` preserves primary score length and applies secondary signal influence.
6. `audio_samples_to_frame_scores()` aligns audio scores to a target length and detects louder frames.

### What is not yet tested

- full `detect_highlights()` integration with real videos
- `frames_to_timestamps()`
- `percentile_threshold()`
- `cut_clips()`
- CLI argument parsing in `src/main.py`

## 17. Current Code Structure

The repository currently contains these implemented processing modules:

- [`src/main.py`](src/main.py): CLI entry point
- [`src/highlight/pipeline.py`](src/highlight/pipeline.py): highlight detection orchestration
- [`src/audio/analysis.py`](src/audio/analysis.py): audio extraction and audio score generation
- [`src/cs2/killfeed.py`](src/cs2/killfeed.py): CS2 kill-feed detection
- [`src/video/motion.py`](src/video/motion.py): motion score extraction and compatibility exports
- [`src/video/clips.py`](src/video/clips.py): clip cutting
- [`src/highlight/windows.py`](src/highlight/windows.py): window utilities
- [`src/highlight/timestamps.py`](src/highlight/timestamps.py): timestamp utilities
- [`src/highlight/scoring.py`](src/highlight/scoring.py): score normalization and fusion
- [`tests/test_motion_utils.py`](tests/test_motion_utils.py): utility tests
- [`tests/test_audio_analysis.py`](tests/test_audio_analysis.py): audio helper tests
- [`tests/test_scoring_utils.py`](tests/test_scoring_utils.py): score helper tests

The `scoring` and `utils` directories are still available for future expansion.

## 18. End-to-End Summary

At a high level, the pipeline works like this:

1. Read the input video path from the CLI or default location.
2. Open the video with OpenCV.
3. Decode frames one by one.
4. Convert each frame to grayscale, extract edges, blur them, and compare against the previous frame.
5. Turn per-frame differences into a motion score.
6. Decode mono audio samples with FFmpeg.
7. Convert audio samples into frame-aligned loudness scores.
8. Extract kill-feed occurrences from the top right of the frame.
9. Normalize and combine motion, audio, and kill-feed scores.
10. Apply kill-feed gating to zero out frames without kills.
11. Aggregate the final score stream into sliding windows.
12. Keep only windows above the 50th percentile.
13. Merge overlapping windows.
14. Drop short events under 0.1 seconds.
15. Expand events backward by analyzing motion to naturally capture action lead-in.
16. Convert surviving windows to dynamic timestamps (8 seconds for short events, continuous for long events).
17. Merge any clips that overlap or are too close together.
18. Use FFmpeg to cut the final clips into the output directory and play a completion sound.
