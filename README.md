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
|  |  `- videos/
|  |- audio/
|  |- highlight/
|  |- scoring/
|  `- utils/
|- clips/                 # generated output clips
|- tests/
|- scripts/
|- data/
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

This will:
1. Read the input video at `src/video/videos/video.mp4`
2. Detect highlight timestamps
3. Export clips to `clips/`

## Notes

- Input/output paths and detection parameters are currently hardcoded for prototype speed.
- For the next iteration, a CLI/config system is recommended.

## Troubleshooting

- `Failed to open video file`: confirm the file exists and path is correct.
- `ffmpeg` not found: add FFmpeg to PATH or install it system-wide.
- No highlights detected: try different gameplay footage or tune thresholding parameters in `src/video/motion.py`.

## License

MIT (see `LICENSE`).
