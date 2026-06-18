import os
import subprocess
from pathlib import Path


def resolve_ffmpeg_executable():
    project_root = Path(__file__).resolve().parents[2]
    local_ffmpeg = project_root / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    return "ffmpeg"


def cut_clips(video_path, timestamps, output_dir="clips"):
    os.makedirs(output_dir, exist_ok=True)

    ffmpeg_bin = resolve_ffmpeg_executable()

    for idx, (start, end) in enumerate(timestamps):
        output_path = os.path.join(output_dir, f"clip_{idx + 1}.mp4")
        command = [
            ffmpeg_bin,
            "-ss",
            str(start),
            "-to",
            str(end),
            "-i",
            video_path,
            "-c",
            "copy",
            output_path,
            "-y",
        ]
        subprocess.run(command, check=True)
