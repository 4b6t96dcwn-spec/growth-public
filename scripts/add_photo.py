#!/usr/bin/env python3
"""
add_photo.py
CLI helper to add photos (or short videos <= 25s) to the growth project.

Thin wrapper around the reorganized utils.add_media (supports both photos and videos).
Videos longer than 25 seconds are rejected with a clear message.

Usage examples:
    python3 scripts/add_photo.py --files IMG_1234.HEIC myclip.mov --source iphone
    python3 scripts/add_photo.py --files /path/to/plant_video.mp4 --notes "360 walk"
"""

import argparse
import sys
from pathlib import Path

# Make "import utils" work when running as `python3 scripts/add_photo.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import add_media, ROOT, MEDIA_DB


def main():
    parser = argparse.ArgumentParser(
        description="Add photo(s) or short video(s) (max 25 seconds) to growth. "
                    "Videos >25s are rejected. Organizes into dated folders + artifacts mirror."
    )
    parser.add_argument(
        "--files", nargs="+", help="One or more photo or video file paths (from iPhone, computer, etc.)"
    )
    parser.add_argument(
        "--source", default="computer", choices=["iphone", "computer", "cloud"],
        help="Where the media came from"
    )
    parser.add_argument("--notes", default="", help="Optional notes for the entry")
    args = parser.parse_args()

    if args.files:
        for f in args.files:
            add_media(f, source=args.source, notes=args.notes)
    else:
        print("Interactive mode not implemented yet. Pass --files.")
        print(f"Project root: {ROOT}")
        print(f"Media database: {MEDIA_DB}")
        print("Example: python3 scripts/add_photo.py --files myphoto.jpg shortclip.mov")


if __name__ == "__main__":
    main()
