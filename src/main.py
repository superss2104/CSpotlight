import argparse
import logging
from pathlib import Path

from video.motion import cut_clips, detect_highlights

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VIDEO_PATH = PROJECT_ROOT / "data" / "videos" / "video.mp4"
LEGACY_VIDEO_PATH = PROJECT_ROOT / "src" / "video" / "videos" / "video.mp4"


def resolve_default_video() -> Path:
    if DEFAULT_VIDEO_PATH.exists():
        return DEFAULT_VIDEO_PATH
    return LEGACY_VIDEO_PATH


def parse_args():
    parser = argparse.ArgumentParser(description="GameViz highlight extraction pipeline.")
    parser.add_argument(
        "--input",
        type=Path,
        default=resolve_default_video(),
        help="Input video path (default: data/videos/video.mp4, falls back to legacy src path).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "clips",
        help="Output directory for generated clips.",
    )
    parser.add_argument(
        "--motion-weight",
        type=float,
        default=None,
        help="Motion score weight for highlight detection.",
    )
    parser.add_argument(
        "--audio-weight",
        type=float,
        default=None,
        help="Audio score weight for highlight detection.",
    )
    parser.add_argument(
        "--killfeed-weight",
        type=float,
        default=None,
        help="Kill-feed score weight for highlight detection.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    video_path = args.input.resolve()
    output_dir = args.output.resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"Input video not found: {video_path}")

    LOGGER.info("GameViz pipeline initialized")
    LOGGER.info("Input video: %s", video_path)
    LOGGER.info("Output directory: %s", output_dir)

    timestamps = detect_highlights(
        str(video_path),
        motion_weight=args.motion_weight,
        audio_weight=args.audio_weight,
        killfeed_weight=args.killfeed_weight,
    )
    LOGGER.info("Detected %d clip windows", len(timestamps))
    LOGGER.debug("Timestamps: %s", timestamps)

    cut_clips(str(video_path), timestamps, output_dir=str(output_dir))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
