# GameViz Pipeline Documentation

This document describes the current end-to-end pipeline implemented in the repository, starting from video loading and ending with generated clip files.

The codebase is currently a small prototype centered around one processing path:

1. Load a single input video.
2. Scan it frame by frame.
3. Compute a motion score for each frame transition.
4. Extract audio loudness scores from the same video.
5. Fuse motion and audio scores into one highlight score stream.
6. Aggregate fused scores into candidate highlight windows.
7. Convert those windows into timestamps.
8. Cut clips with FFmpeg.

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
python src/main.py --motion-weight 0.65 --audio-weight 0.35
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
- [`src/video/motion.py`](src/video/motion.py): visual motion score extraction
- [`src/video/clips.py`](src/video/clips.py): FFmpeg clip extraction
- [`src/highlight/windows.py`](src/highlight/windows.py): sliding windows, percentile filtering, merging, and duration filtering
- [`src/highlight/timestamps.py`](src/highlight/timestamps.py): frame-range to timestamp conversion and clip overlap suppression
- [`src/highlight/scoring.py`](src/highlight/scoring.py): score normalization and motion/audio score fusion

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
(0.70 * rms) + (0.20 * peak) + (0.10 * onset)
```

This keeps sustained loudness as the dominant signal while still giving some weight to spikes and sudden increases.

### 7.3 Safe fallback

If FFmpeg is missing, the video has no audio, audio extraction fails, or audio analysis raises an unexpected exception, the pipeline logs the issue and falls back to motion-only scoring. This preserves the existing pipeline behavior instead of failing highlight detection.

## 8. Score Fusion

Motion and audio scores are combined in [`src/highlight/scoring.py`](src/highlight/scoring.py).

Both signals are normalized to the `0.0` to `1.0` range before fusion. The current weights are:

- Motion: `0.65`
- Audio: `0.35`

The fused score formula is:

```python
combined = 0.65 * normalized_motion + 0.35 * normalized_audio
```

The output score list keeps the motion score length so downstream windowing and timestamp conversion continue to operate on the same frame-based timeline.

Important practical detail: changing weights may change internal score windows without visibly changing the final output clips. After score fusion, the pipeline still applies percentile thresholding, window merging, 8-second timestamp centering, and overlap suppression. Nearby detections can therefore collapse into the same final clip even when the underlying score stream changed.

## 9. Candidate Highlight Window Detection

Once the final highlight score stream is built, [`src/highlight/pipeline.py`](src/highlight/pipeline.py) identifies likely highlight intervals in several stages.

### 6.1 Sliding windows

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

### 6.2 Percentile thresholding

The window scores are filtered using the 60th percentile:

```python
highlight_windows = percentile_threshold(windows)
```

The threshold is computed with `np.percentile(scores, 60)`.

Any window whose score is greater than or equal to the percentile threshold is kept.

This is a relative thresholding strategy:

- It does not use a fixed hardcoded score cut-off.
- It adapts to the motion distribution of the specific video.

### 6.3 Merge overlapping windows

The selected windows are merged with `merge_windows()`.

Behavior:

- Windows are assumed to be in chronological order.
- If the next window starts before or at the current end, or within a small configurable gap, they are merged into one interval.
- Otherwise, the current interval is finalized and a new one begins.

This step collapses contiguous highlight-like regions into larger spans.

## 10. Duration Filtering

After merging, the code filters out short events:

```python
min_event_duration = 0.8
```

For each merged frame range:

```python
duration = (end_frame - start_frame) / fps
```

Only intervals with duration greater than or equal to `0.8` seconds are kept.

This removes brief spikes that are likely too small to be meaningful highlights.

## 11. Frame Ranges to Clip Timestamps

The remaining frame ranges are converted to time ranges by `frames_to_timestamps()` in [`src/highlight/timestamps.py`](src/highlight/timestamps.py).

### 8.1 Center-based timing

For each merged window:

```python
center = (start_frame + end_frame) // 2
```

The clip is centered around that frame.

### 8.2 Clip length

The default clip length is `8.0` seconds.

Half-length is:

```python
half = clip_len / 2
```

So the nominal clip spans approximately 4 seconds before and 4 seconds after the center.

### 8.3 Start bias

The code adds a `0.25` second bias to the start time:

```python
start_bias = 0.25
start_time = max(0, center / fps - half + start_bias)
end_time = center / fps + half
```

This shifts the clip slightly forward.

Practical effect:

- The clip begins a little later than a perfectly symmetric center crop.
- This can keep the most intense part of the event closer to the middle of the output clip.

### 8.4 Non-negative start

`start_time` is clamped to `0` so the clip never begins before the video start.

## 12. Clip Deduplication

The timestamp list is passed through `suppress_overlapping_clips()`.

### Behavior

- The timestamps are sorted.
- The first timestamp is always kept.
- Each later timestamp is compared with the end of the last kept clip.
- If the new start is less than or equal to `last_end + min_gap`, it is discarded.

Default gap:

```python
min_gap = 0.75
```

This prevents nearly overlapping or back-to-back clips from being emitted as separate files.

## 13. Clip Extraction

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

## 14. Test Coverage

The current tests live in [`tests/test_motion_utils.py`](tests/test_motion_utils.py).

They cover pure utility functions exposed through the compatibility layer in [`src/video/motion.py`](src/video/motion.py), plus audio and scoring helpers:

1. `sliding_windows()` adds the tail window correctly.
2. `merge_windows()` merges overlapping frame ranges.
3. `suppress_overlapping_clips()` removes clips that are too close together.
4. `normalize_scores()` scales and handles constant values.
5. `combine_scores()` preserves primary score length and applies secondary signal influence.
6. `audio_samples_to_frame_scores()` aligns audio scores to a target length and detects louder frames.

### What is not yet tested

- full `detect_highlights()` integration with real videos
- `frames_to_timestamps()`
- `percentile_threshold()`
- `cut_clips()`
- CLI argument parsing in `src/main.py`

## 15. Current Code Structure

The repository currently contains these implemented processing modules:

- [`src/main.py`](src/main.py): CLI entry point
- [`src/highlight/pipeline.py`](src/highlight/pipeline.py): highlight detection orchestration
- [`src/audio/analysis.py`](src/audio/analysis.py): audio extraction and audio score generation
- [`src/video/motion.py`](src/video/motion.py): motion score extraction and compatibility exports
- [`src/video/clips.py`](src/video/clips.py): clip cutting
- [`src/highlight/windows.py`](src/highlight/windows.py): window utilities
- [`src/highlight/timestamps.py`](src/highlight/timestamps.py): timestamp utilities
- [`src/highlight/scoring.py`](src/highlight/scoring.py): score normalization and fusion
- [`tests/test_motion_utils.py`](tests/test_motion_utils.py): utility tests
- [`tests/test_audio_analysis.py`](tests/test_audio_analysis.py): audio helper tests
- [`tests/test_scoring_utils.py`](tests/test_scoring_utils.py): score helper tests

The `scoring` and `utils` directories are still available for future expansion.

## 16. End-to-End Summary

At a high level, the pipeline works like this:

1. Read the input video path from the CLI or default location.
2. Open the video with OpenCV.
3. Decode frames one by one.
4. Convert each frame to grayscale, extract edges, blur them, and compare against the previous frame.
5. Turn per-frame differences into a motion score.
6. Decode mono audio samples with FFmpeg.
7. Convert audio samples into frame-aligned loudness scores.
8. Normalize and combine motion/audio scores, or fall back to motion-only if audio is unavailable.
9. Aggregate the final score stream into sliding windows.
10. Keep only windows above the 60th percentile.
11. Merge overlapping windows.
12. Drop short events under 0.8 seconds.
13. Convert surviving windows to approximately 8-second timestamps.
14. Remove timestamps that are too close together.
15. Use FFmpeg to cut the final clips into the output directory.
