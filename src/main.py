import argparse
import logging
import winsound
from pathlib import Path

from video.motion import cut_clips, detect_highlights
from highlight.categories import ClipCategory

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VIDEO_PATH = PROJECT_ROOT / "data" / "videos" / "video.mp4"
LEGACY_VIDEO_PATH = PROJECT_ROOT / "src" / "video" / "videos" / "video.mp4"


def resolve_default_video() -> Path:
    if DEFAULT_VIDEO_PATH.exists():
        return DEFAULT_VIDEO_PATH
    return LEGACY_VIDEO_PATH


def parse_args():
    parser = argparse.ArgumentParser(description="CSpotlight highlight extraction pipeline.")
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
    parser.add_argument(
        "--disable-single-kills",
        action="store_true",
        default=False,
        help="Exclude single-kill clips from the output.",
    )
    parser.add_argument(
        "--disable-multi-kills",
        action="store_true",
        default=False,
        help="Exclude multi-kill clips from the output.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    video_path = args.input.resolve()
    output_dir = args.output.resolve()

    if not video_path.exists():
        raise FileNotFoundError(f"Input video not found: {video_path}")

    LOGGER.info("CSpotlight pipeline initialized")
    LOGGER.info("Input video: %s", video_path)
    LOGGER.info("Output directory: %s", output_dir)

    # Build the set of enabled clip categories from CLI flags.
    enabled_categories = None
    if args.disable_single_kills or args.disable_multi_kills:
        enabled_categories = set(ClipCategory)
        if args.disable_single_kills:
            enabled_categories.discard(ClipCategory.SINGLE_KILL)
        if args.disable_multi_kills:
            enabled_categories.discard(ClipCategory.MULTIPLE_KILLS)
        LOGGER.info("Enabled clip categories: %s",
                    ", ".join(c.name for c in enabled_categories) or "(none)")

    clips = detect_highlights(
        str(video_path),
        motion_weight=args.motion_weight,
        audio_weight=args.audio_weight,
        killfeed_weight=args.killfeed_weight,
        enabled_categories=enabled_categories,
    )
    LOGGER.info("Detected %d clip windows", len(clips))
    for i, clip in enumerate(clips):
        LOGGER.debug("  Clip %d: %.2fs - %.2fs  [%s]", i + 1, clip.start, clip.end, clip.category.name)

    # CategorizedClip supports tuple unpacking, so cut_clips works as-is.
    timestamps = [(clip.start, clip.end) for clip in clips]
    cut_clips(str(video_path), timestamps, output_dir=str(output_dir))
    LOGGER.info("Done — %d clips saved to %s", len(clips), output_dir)
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    main()
