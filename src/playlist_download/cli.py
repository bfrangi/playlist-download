"""Download the audio track of every video in a YouTube playlist."""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.common import PostProcessor

FORMATS = ("mp3", "m4a", "opus", "flac", "wav")

YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
        "www.youtu.be",
    }
)

# Archive of finished video IDs, kept alongside the audio. Its presence is what
# makes a second run cheap: yt-dlp skips anything listed here.
ARCHIVE_NAME = ".downloaded.txt"

# Each naming component emits "<value> - " when its field is present and
# nothing at all when it is absent, so a missing artist or album takes its
# separator with it instead of leaving " - - " in the filename.
ARTIST_FIELD = "%(artist&{} - |)s"
ALBUM_FIELD = "%(album&{} - |)s"
# `track` falls back to `title`: some sources supply a clean song name in
# metadata, while an ordinary upload only has the video title (often cluttered
# with "(Official Video)" and similar).
SONG_FIELD = "%(track,title)s"
# Dropped for a single video, which would otherwise be saved as "NA - Title".
NUMBER_FIELD = "%(playlist_index&{:03d} - |)s"

DEFAULT_TEMPLATE = f"{ARTIST_FIELD}{ALBUM_FIELD}{SONG_FIELD}"


def _package_version() -> str:
    try:
        return version("playlist-download")
    except PackageNotFoundError:  # running from a source checkout
        return "unknown"


def normalize_url(url: str) -> str:
    """Strip backslashes left behind by shell paste helpers.

    zsh's url-quote-magic escapes `?` and `=` when a URL is pasted. Inside
    double quotes those backslashes survive into argv, producing a URL that
    silently misroutes. No real URL contains a backslash, so dropping them is
    safe.
    """
    cleaned = url.replace("\\", "")
    if cleaned != url:
        print(f"note: removed backslashes from the URL -> {cleaned}", file=sys.stderr)
    return cleaned


def check_is_downloadable(url: str) -> None:
    """Reject YouTube URLs that address a feed rather than a video or playlist.

    A malformed watch URL redirects to the YouTube home page, where yt-dlp will
    happily start downloading the viewer's "recommended" feed. Failing loudly
    here beats quietly fetching the wrong thing.
    """
    parsed = urlparse(url)
    if parsed.netloc.lower() not in YOUTUBE_HOSTS:
        return  # another site entirely; let yt-dlp decide

    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query)

    problem = None
    if path in ("", "/feed") or path.startswith("/feed/"):
        problem = "points at a YouTube feed, not a video or playlist"
    elif path == "/watch" and "v" not in query:
        problem = "is a /watch URL with no v= video ID"
    elif path == "/playlist" and "list" not in query:
        problem = "is a /playlist URL with no list= playlist ID"

    if problem:
        raise SystemExit(
            f"error: that URL {problem}.\n"
            f"  got: {url}\n"
            "  expected something like:\n"
            "    https://www.youtube.com/watch?v=VIDEO_ID\n"
            "    https://www.youtube.com/playlist?list=PLAYLIST_ID\n"
            "  If your shell added backslashes when you pasted, wrap the URL in "
            "single quotes instead."
        )


def escape_literal(text: str) -> str:
    """Make user-supplied text safe to embed in a yt-dlp output template.

    `%` starts a field, and a path separator would silently create directories.
    """
    return text.replace("%", "%%").replace("/", "-").replace("\\", "-").strip()


def _looks_like_single_video(url: str) -> bool:
    """True when the URL addresses one video rather than a playlist."""
    parsed = urlparse(url)
    if parsed.netloc.lower().endswith("youtu.be"):
        return True
    query = parse_qs(parsed.query)
    return "v" in query and "list" not in query


def build_template(
    album: str | None = None,
    artist: str | None = None,
    song: str | None = None,
    number: bool = False,
) -> str:
    """Build the filename template from three optional components.

    Each of artist, album and song resolves in the same order: an explicit
    command-line value, else the value carried by the video's own metadata,
    else omitted entirely along with its separator. A video with no music
    metadata and no overrides is therefore named after its title alone.
    """
    parts = []
    if number:
        parts.append(NUMBER_FIELD)
    parts.append(f"{escape_literal(artist)} - " if artist else ARTIST_FIELD)
    parts.append(f"{escape_literal(album)} - " if album else ALBUM_FIELD)
    parts.append(escape_literal(song) if song else SONG_FIELD)
    return "".join(parts)


class TagOverridePP(PostProcessor):
    """Write the command-line artist/album/song into the file's own tags.

    The metadata post-processor maps any `meta_<name>` key in the info dict
    straight onto the output tag of that name, overriding whatever it derived
    from the video. Injecting them before the download keeps the embedded tags
    consistent with the filename, instead of the filename saying one thing and
    the tags another.
    """

    def __init__(self, overrides: dict[str, str]) -> None:
        super().__init__()
        self._overrides = overrides

    def run(self, info):
        info.update(self._overrides)
        return [], info


def build_tag_overrides(
    album: str | None, artist: str | None, song: str | None
) -> dict[str, str]:
    """Map the naming overrides onto the tag names the file should carry."""
    overrides = {}
    if artist:
        overrides["meta_artist"] = artist
        # Players group an album by album_artist, not artist; without this a
        # compilation-style album scatters across the library.
        overrides["meta_album_artist"] = artist
    if album:
        overrides["meta_album"] = album
    if song:
        overrides["meta_title"] = song
    return overrides


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
    template: str = DEFAULT_TEMPLATE,
    restrict_filenames: bool = False,
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
        "outtmpl": str(output_dir / f"{template}.%(ext)s"),
        "download_archive": str(output_dir / ARCHIVE_NAME),
        # Without this the playlist's own cover is written as a stray image
        # next to the tracks, named after the album rather than any song.
        "allow_playlist_files": False,
        "restrictfilenames": restrict_filenames,
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
        "--artist",
        metavar="NAME",
        help="override the artist part of the filename (default: the video's own tag)",
    )
    parser.add_argument(
        "--album",
        metavar="NAME",
        help="override the album part of the filename (default: the video's own tag)",
    )
    parser.add_argument(
        "--song",
        metavar="NAME",
        help=(
            "override the song part of the filename (default: the video's track "
            "tag, else its title)"
        ),
    )
    parser.add_argument(
        "--number",
        action="store_true",
        help="prefix each file with its position in the playlist",
    )
    parser.add_argument(
        "--ascii-filenames",
        action="store_true",
        help="strip accents and spaces from filenames (breaks 'Niño' into 'Nino')",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    url = normalize_url(args.url)
    check_is_downloadable(url)

    if args.song and args.items != "1" and not _looks_like_single_video(url):
        # One fixed song name across a playlist would give every track the same
        # filename, and nooverwrites would then discard all but the first.
        print(
            "warning: --song names every downloaded file identically; it is "
            "meant for a single video.",
            file=sys.stderr,
        )

    output_dir: Path = args.output.expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    options = build_options(
        output_dir=output_dir,
        audio_format=args.audio_format,
        quality=args.quality,
        embed_thumbnail=not args.no_thumbnail,
        playlist_items=args.items,
        template=build_template(args.album, args.artist, args.song, args.number),
        restrict_filenames=args.ascii_filenames,
    )

    overrides = build_tag_overrides(args.album, args.artist, args.song)

    try:
        with YoutubeDL(options) as ydl:
            if overrides:
                # 'pre_process' so the keys exist before the metadata stage.
                ydl.add_post_processor(TagOverridePP(overrides), when="pre_process")
            exit_code = ydl.download([url])
    except KeyboardInterrupt:
        print("\nInterrupted. Re-run the same command to resume.", file=sys.stderr)
        raise SystemExit(130)

    count = len([p for p in output_dir.iterdir() if p.suffix == f".{args.audio_format}"])
    print(f"\n{count} {args.audio_format} file(s) in {output_dir}")

    if count == 0 and exit_code:
        # A playlist index can be public while its entries are not playable.
        print(
            "Nothing was downloaded: every item failed.\n"
            "If they all said 'Video unavailable', the playlist lists entries "
            "that are not available for download. Listing succeeds because a "
            "playlist index stays public even when its entries are not.",
            file=sys.stderr,
        )
    elif exit_code:
        # ignoreerrors means we get here with skipped videos rather than a crash.
        print("Some videos could not be downloaded (see errors above).", file=sys.stderr)

    raise SystemExit(exit_code)
