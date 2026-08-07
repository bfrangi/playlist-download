# playlist-download

Download the audio from a YouTube playlist as tagged MP3s.

No system dependencies — ffmpeg and the JavaScript runtime YouTube extraction
needs are both installed as Python wheels. If you have [uv], you have
everything.

## Run it

```sh
uvx --from git+https://github.com/bfrangi/playlist-download playlist-download \
    'https://www.youtube.com/playlist?list=PLxxxxxxxx'
```

That downloads, runs, and throws the environment away. Nothing is installed.

## Install it

To get a permanent `playlist-download` command on your PATH:

```sh
uv tool install git+https://github.com/bfrangi/playlist-download
playlist-download 'https://www.youtube.com/playlist?list=PLxxxxxxxx'
```

Upgrade later with `uv tool upgrade playlist-download`, remove it with
`uv tool uninstall playlist-download`.

Don't have uv? One line, no admin rights, no Python needed first:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh          # macOS / Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

## Usage

```
playlist-download [-o DIR] [-f FORMAT] [-q QUALITY] [--no-thumbnail] [--items SPEC] URL
```

| Option | Default | Meaning |
| --- | --- | --- |
| `-o`, `--output` | `./downloads` | Where the files go |
| `-f`, `--format` | `mp3` | `mp3`, `m4a`, `opus`, `flac`, `wav` |
| `-q`, `--quality` | `0` | 0–10 VBR (0 is best), or a bitrate like `192K` |
| `--no-thumbnail` | off | Skip embedding cover art |
| `--items` | all | A subset: `1-10`, `3,7,12`, `5:` |

Files land as `001 - track_title.mp3`, numbered by playlist position, with
title, artist, date, chapters, and cover art embedded.

### Resuming

Re-run the exact same command. Finished video IDs are recorded in
`.downloaded.txt` inside the output directory, so a second run skips what's
already there and fetches only what's new. This covers both an interrupted
download and a playlist that has grown since last time.

To force a re-download, delete that file (or the individual tracks).

### Examples

```sh
# A whole playlist into a specific folder
playlist-download -o ~/Music/roadtrip 'https://www.youtube.com/playlist?list=PLxxxxxxxx'

# Smaller files
playlist-download -q 192K 'https://www.youtube.com/playlist?list=PLxxxxxxxx'

# Just the first ten, as lossless FLAC
playlist-download --items 1-10 -f flac 'https://www.youtube.com/playlist?list=PLxxxxxxxx'

# A single video also works
playlist-download 'https://www.youtube.com/watch?v=xxxxxxxxxxx'
```

A private, deleted, or region-blocked video in the middle of a playlist is
reported and skipped rather than aborting the run.

## Development

```sh
git clone https://github.com/bfrangi/playlist-download
cd playlist-download
uv run playlist-download --help
```

`uv run` creates the virtualenv and installs dependencies on first use.

YouTube changes break extraction periodically; the fix is almost always a newer
yt-dlp. Bump it with `uv lock --upgrade-package yt-dlp`.

## Note

Download only what you have the right to: your own uploads, Creative Commons
material, public-domain works, or content whose licence permits it.

[uv]: https://docs.astral.sh/uv/
