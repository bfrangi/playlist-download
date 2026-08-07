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
playlist-download [-o DIR] [-f FORMAT] [-q QUALITY] [--no-thumbnail]
                  [--items SPEC] [--album NAME] [--artist NAME]
                  [--ascii-filenames] URL
```

| Option | Default | Meaning |
| --- | --- | --- |
| `-o`, `--output` | `./downloads` | Where the files go |
| `-f`, `--format` | `mp3` | `mp3`, `m4a`, `opus`, `flac`, `wav` |
| `-q`, `--quality` | `0` | 0–10 VBR (0 is best), or a bitrate like `192K` |
| `--no-thumbnail` | off | Skip embedding cover art |
| `--items` | all | A subset: `1-10`, `3,7,12`, `5:` |
| `--album` | off | Name files `<artist> - <album> - <song>` |
| `--artist` | track's own tag | Artist to use with `--album` |
| `--ascii-filenames` | off | Strip accents and spaces from filenames |

By default files land as `001 - Song Name.mp3`, numbered by playlist position,
with title, artist, date, chapters, and cover art embedded. A single video is
saved as just `Song Name.mp3`, with no number.

### Naming for a music library

Playlist numbering is the wrong shape for an album you want to browse by name.
`--album` switches to `<artist> - <album> - <song>`:

```sh
playlist-download --album 'Días de Invierno' --artist 'Río Norte' \
    -o 'albums/Dias de Invierno' 'https://www.youtube.com/playlist?list=PLxxxxxxxx'
```

```
Río Norte - Días de Invierno - Corazón de Piedra.mp3
```

Leave `--artist` off to take the artist from each track's own metadata.

The song name comes from the track tag where one exists. Some sources supply a
clean song title in metadata; an ordinary channel upload often has no track tag
at all, in which case the video title is used verbatim — including any
"(Official Video)" padding the uploader put there. Check one file before
committing to a whole album.

Accented characters are kept as-is, so `Corazón` stays spelled correctly. Pass
`--ascii-filenames` if you need plain ASCII for an old car stereo or a FAT32
stick, at the cost of turning it into `Corazon`.

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

## Troubleshooting

**Always quote the URL, and never combine quotes with backslashes.** Pasting a
URL into zsh can insert backslashes before `?` and `=`. Inside double quotes
those backslashes are literal, so the URL is silently wrong:

```sh
playlist-download "https://www.youtube.com/watch\?v\=VIDEO_ID"   # broken
playlist-download 'https://www.youtube.com/watch?v=VIDEO_ID'     # correct
```

Stray backslashes are stripped automatically, and a URL that points at the
YouTube home page or a feed is rejected rather than quietly downloading your
recommended videos.

**Every track says "Video unavailable"?** A playlist index stays public even
when its entries are not playable, so listing a playlist can succeed while
every download fails. Ordinary uploads on a channel are unaffected.

**Extraction suddenly failing?** YouTube changes break yt-dlp periodically. Get
a newer one with `uv tool upgrade playlist-download`, or from a checkout:

```sh
uv lock --upgrade-package yt-dlp
```

## Development

```sh
git clone https://github.com/bfrangi/playlist-download
cd playlist-download
uv run playlist-download --help
```

`uv run` creates the virtualenv and installs dependencies on first use.

## Note

Download only what you have the right to: your own uploads, Creative Commons
material, public-domain works, or content whose licence permits it.

[uv]: https://docs.astral.sh/uv/
