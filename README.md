# CSpotlight

CSpotlight is a highlight-detection pipeline for CS2 gameplay footage.
It fuses motion, audio, and killfeed signals to automatically identify and cut
the most exciting moments from a recording.

## Features

- **Multi-signal scoring** — combines motion (OpenCV optical flow), audio energy,
  and CS2 killfeed detection into a single fused score stream
- **Killfeed detection** — locates red-outlined kill entries in the HUD using
  contour analysis; rejects filled death-screen elements via inner-fill heuristics
- **Multikill detection** — groups kill events within a sliding time window
  (with debounce) to identify double/triple/quad kills
- **Clip categorization** — tags each output clip as `SINGLE_KILL` or
  `MULTIPLE_KILLS` and supports category-based filtering
- **Motion-expansion** — extends clip boundaries backward using motion analysis
  to capture the full action leading into a highlight
- **Clip merging** — adjacent clips are merged to prevent fragmented output
- **Automatic clip cutting** — extracts final clips with FFmpeg; local binary
  resolved automatically if not on PATH
- **Desktop notification** — plays a system beep when processing finishes

## Project Structure

```text
CSpotlight/
|- src/
|  |- main.py                    # CLI entry point
|  |- quick_test.py              # diagnostic visualizer for killfeed detector
|  |- cs2/
|  |  |- killfeed.py             # killfeed frame analysis, KillfeedResult
|  |  `- multikill.py            # multikill event detection and frame mask
|  |- highlight/
|  |  |- pipeline.py             # main detect_highlights() orchestration
|  |  |- categories.py           # ClipCategory enum, CategorizedClip, filtering
|  |  |- scoring.py              # score fusion helpers
|  |  |- timestamps.py           # clip window selection
|  |  `- windows.py              # sliding-window utilities
|  |- audio/                     # audio energy extraction
|  |- video/
|  |  `- motion.py               # optical-flow motion scoring, clip cutting
|  |- scoring/
|  `- utils/
|- tests/
|  |- test_killfeed.py
|  |- test_multikill.py
|  |- test_categories.py
|  `- test_pipeline_scoring.py
|- clips/                        # generated output clips
|- data/
|  `- videos/                    # preferred input location
|- requirements.txt
`- README.md
```

## Requirements

- Python 3.10+ (3.11 recommended)
- FFmpeg installed and available on PATH (or discoverable locally)
- Python packages listed in `requirements.txt`

## Setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Verify FFmpeg:

```powershell
ffmpeg -version
```

## Run

From the project root:

```powershell
python src/main.py
```

By default this uses:
- **Input:** `data/videos/video.mp4` (falls back to `src/video/videos/video.mp4`)
- **Output:** `clips/`

### CLI Options

```
--input PATH             Path to input video file
--output PATH            Directory for output clips
--motion-weight FLOAT    Weight for motion signal  (default 0.25)
--audio-weight FLOAT     Weight for audio signal   (default 0.25)
--killfeed-weight FLOAT  Weight for killfeed signal (default 0.50)
--disable-single-kills   Exclude single-kill clips from output
--disable-multi-kills    Exclude multi-kill clips from output
```

**Examples:**

```powershell
# Run with explicit paths
python src/main.py --input "data/videos/match.mp4" --output "clips/match"

# Multi-kill highlights only
python src/main.py --input "data/videos/match.mp4" --disable-single-kills

# Boost killfeed signal
python src/main.py --killfeed-weight 0.7 --motion-weight 0.2 --audio-weight 0.1
```

## Running Tests

```powershell
python -m pytest tests/
```

## Troubleshooting

- **`Failed to open video file`** — confirm the path exists and FFmpeg can decode the format.
- **`ffmpeg` not found** — add FFmpeg to PATH or place the binary inside the project.
- **No highlights detected** — try different footage or tune thresholding in `src/highlight/pipeline.py`.
- **False multikill detections** — adjust `DEBOUNCE_COOLDOWN_SECONDS` in `src/cs2/multikill.py`.

## License

MIT (see `LICENSE`).
