import os
import subprocess


def cut_clips(video_path, timestamps, output_dir="clips"):
    os.makedirs(output_dir, exist_ok=True)

    for idx, (start, end) in enumerate(timestamps):
        output_path = os.path.join(output_dir, f"clip_{idx + 1}.mp4")
        command = [
            "ffmpeg",
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
