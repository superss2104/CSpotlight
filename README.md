# GameViz (Prototype)

GameViz is a prototype video-highlighting pipeline for gameplay clips.
It detects motion-heavy segments and automatically cuts short highlight clips using FFmpeg.

## Current Status

This repository is an early prototype focused on:
- Motion-based highlight detection
- Timestamp generation
- Clip extraction

Planned modules (`audio`, `highlight`, `scoring`, `utils`) are scaffolded for future features.

## Features (Current)

- Frame-by-frame motion scoring with OpenCV
- Sliding-window highlight selection (percentile thresholding)
- Overlap suppression for cleaner clip outputs
- Automatic clip cutting via FFmpeg

## Project Structure

```text
GameViz/
|- src/
|  |- main.py
|  |- video/
|  |  |- motion.py
|  |  `- videos/           # legacy prototype sample location
|  |- audio/
|  |- highlight/
|  |- scoring/
|  `- utils/
|- clips/                 # generated output clips
|- tests/
|- scripts/
|- data/
|  `- videos/              # preferred input location
|- requirements.txt
`- README.md
```

## Requirements

- Python 3.10+ (3.11 recommended)
- FFmpeg installed and available on PATH
- Python packages in `requirements.txt`

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

By default, this uses:
- Input: `data/videos/video.mp4` (falls back to legacy `src/video/videos/video.mp4`)
- Output: `clips/`

You can also pass explicit paths:

```powershell
python src/main.py --input "path/to/video.mp4" --output "clips/my_run"
```

## Notes

- Detection parameters are still tuned as prototype defaults in `src/video/motion.py`.

## Troubleshooting

- `Failed to open video file`: confirm the file exists and path is correct.
- `ffmpeg` not found: add FFmpeg to PATH or install it system-wide.
- No highlights detected: try different gameplay footage or tune thresholding parameters in `src/video/motion.py`.

## License

MIT (see `LICENSE`).
