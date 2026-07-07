# SpotTagger

Tag your audio files with metadata from Spotify, MusicBrainz, or your local Spotify player — no account required for most modes.

Supports MP3, M4A, Opus. Embeds title, artist, album, and cover artwork. Comes with both a GTK desktop GUI and a CLI.

## Features

- **Three metadata sources** — Spotify API, MusicBrainz Search, or Local Player (reads your running Spotify client)
- **AcoustID fingerprinting** — identify songs by audio fingerprint (requires a free AcoustID API key)
- **Embed cover art** — high-quality album artwork into the file
- **Spotify Local Files** — copy tagged files to your Spotify local files folder automatically
- **Drop-dead simple GUI** — drag & drop files, paste a URL, click Tag & Save
- **Full CLI** — scriptable, headless tagging

## Modes

| Mode | Credentials Needed | What it does |
|---|---|---|
| **Spotify API** | Client ID + Secret (from developer.spotify.com) | Paste a Spotify track URL, fetches metadata via the official API |
| **MusicBrainz Search** | **None** | Type a track name (`Track — Artist`) and it searches the open MusicBrainz database |
| **Local Player** | **None** | Reads whatever is currently playing in your local Spotify desktop app via MPRIS |
| **Auto (AcoustID)** | Free AcoustID key (acoustid.org) | Fingerprints the audio file and looks up the match on MusicBrainz |

## Screenshots

![Main Window](docs/images/main-window.png)

## Quick Start

### 1. Setup

```bash
./setup.sh
```

This creates a virtualenv and installs dependencies.

### 2. System Dependencies

**AcoustID fingerprinting** needs `libchromaprint`:
```bash
# Debian / Ubuntu / Mint
sudo apt install libchromaprint-dev

# Arch
sudo pacman -S chromaprint
```

**Local Player mode** needs `playerctl`:
```bash
# Debian / Ubuntu / Mint
sudo apt install playerctl

# Arch
sudo pacman -S playerctl
```

### 3. Get API Keys (optional)

Only needed if you use Spotify API or AcoustID modes:
- **Spotify:** Create an app at https://developer.spotify.com, grab Client ID + Secret
- **AcoustID:** Get a free key at https://acoustid.org/

### 4. Use It

#### CLI

```bash
# Spotify API mode
./stag song.mp3 https://open.spotify.com/track/... --id CLIENT_ID --secret CLIENT_SECRET

# MusicBrainz Search mode (no keys)
./stag song.mp3 "Never Gonna Give You Up — Rick Astley" --musicbrainz

# Local Player mode (no keys — reads from running Spotify desktop)
./stag song.mp3 --from-player

# AcoustID fingerprinting mode (free key required)
export ACOUSTID_API_KEY=your_key
./stag song.mp3 --acoustid
```

#### GUI

```bash
./launch.sh
```

## CLI Reference

```
usage: spotify_tagger.py [-h] [--id CLIENT_ID] [--secret CLIENT_SECRET]
                         [--no-cover] [--acoustid]
                         [--acoustid-api-key ACOUSTID_API_KEY]
                         [--musicbrainz] [--from-player]
                         audio [track]

positional arguments:
  audio                 Path to the audio file (.mp3, .m4a, .opus)
  track                 Spotify URL/ID, or search query for --musicbrainz

options:
  --id CLIENT_ID          Spotify Client ID (or SPOTIPY_CLIENT_ID env var)
  --secret CLIENT_SECRET  Spotify Client Secret (or SPOTIPY_CLIENT_SECRET env var)
  --no-cover              Skip embedding cover art
  --acoustid              Use AcoustID fingerprinting
  --acoustid-api-key KEY  AcoustID API key (or ACOUSTID_API_KEY env var)
  --musicbrainz           Search MusicBrainz by track name (no API keys)
  --from-player           Read now-playing from local Spotify (no API keys)
```

## Project Structure

```
├── spotify_tagger.py       # Core CLI — tagging logic
├── spotify_tagger_app.py   # GTK3 GUI
├── setup.sh                # One-shot setup (creates venv, installs deps)
├── launch.sh               # GUI launcher
├── stag                    # CLI launcher
├── AGENTS.md               # Notes for AI coding assistants
├── spotify-tagger.desktop  # Linux .desktop entry
├── docs/
│   └── images/
│       └── main-window.png
└── README.md
```

## Release History

- **v1.0.0** — MusicBrainz Search, Local Player mode, AcoustID key fix, credential persistence, auto-fetch on URL paste, proper README
- **v0.1.0** — Original release: Spotify API + AcoustID fingerprinting, GTK GUI, CLI
