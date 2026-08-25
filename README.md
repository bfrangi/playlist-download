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
                  [--items SPEC] [--artist NAME] [--album NAME] [--song NAME]
                  [--number] [--ascii-filenames] URL
```

| Option | Default | Meaning |
| --- | --- | --- |
| `-o`, `--output` | `./downloads` | Where the files go |
| `-f`, `--format` | `mp3` | `mp3`, `m4a`, `opus`, `flac`, `wav` |
| `-q`, `--quality` | `0` | 0–10 VBR (0 is best), or a bitrate like `192K` |
| `--no-thumbnail` | off | Skip embedding cover art |
| `--items` | all | A subset: `1-10`, `3,7,12`, `5:` |
| `--artist` | the video's tag | Override the artist part of the filename |
| `--album` | the video's tag | Override the album part of the filename |
| `--song` | track tag, else title | Override the song part of the filename |
| `--number` | off | Prefix each file with its playlist position |
| `--ascii-filenames` | off | Strip accents and spaces from filenames |

Files are named `<artist> - <album> - <song>.mp3`, with title, artist, date,
chapters, and cover art embedded in the file itself.

### Filenames

Each of the three parts resolves the same way:

1. the value you pass on the command line, else
2. the value carried by the video's own metadata, else
3. nothing at all — the part is dropped along with its separator.

So a video tagged with full music metadata gives:

```
Río Norte - Días de Invierno - Corazón de Piedra.mp3
```

while an ordinary upload carrying no artist or album tags gives just:

```
Song Name.mp3
```

No empty ` - - ` is left behind. Override any part you like:

```sh
playlist-download --artist 'Río Norte' --album 'Días de Invierno' \
    -o 'albums/Dias de Invierno' 'https://www.youtube.com/playlist?list=PLxxxxxxxx'
```

Anything you pass is also written into the file's own tags, so the filename and
the embedded metadata agree rather than disagreeing. `--artist` additionally
sets `album_artist`, which is what music players group an album by. Without
overrides the tags come from the video as before.

`--song` names every file identically, so it only makes sense for a single
video; the tool warns if you use it on a playlist. Add `--number` to prefix
each file with its playlist position (`001 - `), which is dropped automatically
for a single video.

The song part prefers the track tag over the video title. Some sources supply a
clean song title in metadata; an ordinary channel upload often has no track tag
at all, in which case the video title is used verbatim — including any
"(Official Video)" padding the uploader put there. Check one file before
committing to a whole album.

### Portable filenames

Before saving, the filename is narrowed to what is legal on Linux, Windows,
macOS and Android at once — Android's shared storage is usually FAT32 or exFAT,
so Windows' rules are the ones that bind. **Only the filename is changed; the
tags inside the file keep their original punctuation.**

| In the title | In the filename |
| --- | --- |
| `What? Really: yes` | `What Really yes` |
| `Simon & Garfunkel` | `Simon and Garfunkel` |
| `AC/DC \ Live` | `AC-DC - Live` |
| `Song ｜ Channel` | `Song - Channel` |
| `He said "hi"` | `He said 'hi'` |

Worth knowing: yt-dlp substitutes full-width look-alikes (`：`, `？`, `｜`) for
reserved characters rather than removing them, which is legal everywhere but
reads as mojibake. Those are undone too.

Also handled: control characters, collapsed whitespace, a leading dot that
would hide the file, a trailing dot or space that Windows silently discards,
Windows device names (`CON`, `NUL`, `COM1`…), and the 255-**byte** length cap,
truncated on a character boundary so an accent is never cut in half.

The output directory from `-o` gets the same treatment, one component at a
time. Separators are preserved, so `-o 'albums/Simon & G: What?'` becomes
`albums/Simon and G What` rather than collapsing into a single folder. A leading
`/`, a Windows drive letter (`C:\`) and `.` / `..` are left alone — the `:` in a
drive letter is legitimate, unlike one in a name. The tool prints a note
whenever it adjusts the path you asked for.

The mapping lives in `FILENAME_REPLACEMENTS` in
[cli.py](src/playlist_download/cli.py) — one dict, `key` replaced by `value`,
an empty value meaning "delete". `&` → `and` is the only entry not required for
compatibility; it is there because `&` needs quoting in a shell one-liner, so
delete that line if you would rather keep it.

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
