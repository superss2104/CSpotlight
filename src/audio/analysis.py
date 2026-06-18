import logging
import subprocess
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__) #the value of __name__ depends on how the module is run. If it's imported then it's value will be the name of the module, in this case analysis. But if it's run directly then a special value called __main__ is assigned
DEFAULT_AUDIO_SAMPLE_RATE = 16000 #16k audio samples per second


def resolve_ffmpeg_executable():
    # Go 3 levels up from this file's absolute path to find the project root.
    # analysis.py -> audio -> src -> CSpotlight (parents[2] = project root)
    project_root = Path(__file__).resolve().parents[2]
    local_ffmpeg = project_root / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)
    return "ffmpeg"


def extract_audio_scores(video_path, fps, target_length, sample_rate=DEFAULT_AUDIO_SAMPLE_RATE):
    if target_length <= 0:
        return []

    samples = decode_audio_samples(video_path, sample_rate=sample_rate)
    if samples.size == 0:
        return []

    frame_scores = audio_samples_to_frame_scores(samples, fps, target_length, sample_rate)
    LOGGER.info("Extracted %d audio scores", len(frame_scores))
    return frame_scores


def decode_audio_samples(video_path, sample_rate=DEFAULT_AUDIO_SAMPLE_RATE):
    command = [
        resolve_ffmpeg_executable(),
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "s16le",
        "-",
    ]

    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        LOGGER.warning("Audio extraction failed for %s: %s", video_path, exc)
        return np.array([], dtype=np.float32) #return empty numpy array of type float32

    # Convert raw 16-bit PCM audio bytes into normalized float32 samples.
    raw_samples = np.frombuffer(completed.stdout, dtype=np.int16)
    return raw_samples.astype(np.float32) / 32768.0


def audio_samples_to_frame_scores(samples, fps, target_length, sample_rate=DEFAULT_AUDIO_SAMPLE_RATE):
    if samples.size == 0 or fps <= 0 or target_length <= 0:
        return []

    samples_per_frame = sample_rate / fps
    scores = []
    previous_rms = 0.0

    for frame_idx in range(target_length):
        start = int(round(frame_idx * samples_per_frame))
        end = int(round((frame_idx + 1) * samples_per_frame))
        chunk = samples[start:end]

        if chunk.size == 0:
            scores.append(0.0)
            continue

        rms = float(np.sqrt(np.mean(np.square(chunk))))
        peak = float(np.max(np.abs(chunk)))
        onset = max(0.0, rms - previous_rms) #onset refers to the transition of the audio from silence to sound
        scores.append((0.40 * rms) + (0.30 * peak) + (0.30 * onset)) #rms has the highest weight which indicates prolonged action
        #peak is useful to capture sudden sounds such as the shot of an awp
        #onset is used to capture the exact moment when an event occurs.
        previous_rms = rms

    return scores
