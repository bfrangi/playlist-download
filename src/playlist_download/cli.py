"""Download the audio track of every video in a YouTube playlist."""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from yt_dlp import YoutubeDL

FORMATS = ("mp3", "m4a", "opus", "flac", "wav")

# Archive of finished video IDs, kept alongside the audio. Its presence is what
# makes a second run cheap: yt-dlp skips anything listed here.
ARCHIVE_NAME = ".downloaded.txt"


def _package_version() -> str:
    try:
        return version("playlist-download")
    except PackageNotFoundError:  # running from a source checkout
        return "unknown"


def find_ffmpeg() -> str:
    """Locate an ffmpeg binary, preferring one already on PATH.

    A system ffmpeg is usually newer and smaller than the wheel-bundled copy,
    but we ship imageio-ffmpeg so the tool still works on a machine that has
    never installed one.
    """
    system = shutil.which("ffmpeg")
    if system:
        return system

    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def build_options(
    output_dir: Path,
    audio_format: str,
    quality: str,
    embed_thumbnail: bool,
    playlist_items: str | None,
) -> dict:
    postprocessors: list[dict] = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": quality,
        },
        {"key": "FFmpegMetadata", "add_metadata": True},
    ]

    if embed_thumbnail:
        # YouTube serves webp thumbnails, which most players won't render as
        # cover art. Convert before embedding.
        postprocessors.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg"})
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    options = {
        "format": "bestaudio/best",
        "postprocessors": postprocessors,
        "writethumbnail": embed_thumbnail,
        "ffmpeg_location": find_ffmpeg(),
        "outtmpl": str(output_dir / "%(playlist_index)03d - %(title)s.%(ext)s"),
        "download_archive": str(output_dir / ARCHIVE_NAME),
        "restrictfilenames": True,
        # One private or region-blocked video shouldn't abort the playlist.
        "ignoreerrors": True,
        "continuedl": True,
        "overwrites": False,
        "retries": 10,
        "concurrent_fragment_downloads": 4,
    }

    if playlist_items:
        options["playlist_items"] = playlist_items

    return options


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="playlist-download",
        description="Download every track of a YouTube playlist as audio files.",
        epilog=(
            "Re-run the same command to resume an interrupted download or to "
            "pick up tracks added to the playlist since last time."
        ),
    )
    parser.add_argument("url", help="playlist URL (a single video URL also works)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("downloads"),
        metavar="DIR",
        help="where to put the files (default: ./downloads)",
    )
    parser.add_argument(
        "-f",
        "--format",
        dest="audio_format",
        choices=FORMATS,
        default="mp3",
        help="audio format (default: mp3)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="0",
        help="0-10 VBR where 0 is best, or a bitrate like 192K (default: 0)",
    )
    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="skip embedding cover art",
    )
    parser.add_argument(
        "--items",
        metavar="SPEC",
        help="download a subset, e.g. '1-10' or '3,7,12' or '5:'",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    output_dir: Path = args.output.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    options = build_options(
        output_dir=output_dir,
        audio_format=args.audio_format,
        quality=args.quality,
        embed_thumbnail=not args.no_thumbnail,
        playlist_items=args.items,
    )

    try:
        with YoutubeDL(options) as ydl:
            exit_code = ydl.download([args.url])
    except KeyboardInterrupt:
        print("\nInterrupted. Re-run the same command to resume.", file=sys.stderr)
        raise SystemExit(130)

    count = len([p for p in output_dir.iterdir() if p.suffix == f".{args.audio_format}"])
    print(f"\n{count} {args.audio_format} file(s) in {output_dir}")

    if exit_code:
        # ignoreerrors means we get here with skipped videos rather than a crash.
        print("Some videos could not be downloaded (see errors above).", file=sys.stderr)

    raise SystemExit(exit_code)
