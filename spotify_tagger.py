#!/usr/bin/env python3
"""
spotify_tagger.py — Fetch Spotify metadata and tag audio files (mp3, m4a, opus)
"""

import argparse
import os
import sys
import re
import tempfile
import requests

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture
import base64

import acoustid


# ─── Constants ────────────────────────────────────────────────────────────────

ACOUSTID_DEFAULT_KEY = "8XVB9HvQ5e"
MB_USER_AGENT = "SpotTagger/1.0"


# ─── Spotify helpers ──────────────────────────────────────────────────────────

def build_spotify_client(client_id: str, client_secret: str) -> spotipy.Spotify:
    creds = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    return spotipy.Spotify(auth_manager=creds)


def extract_track_id(url_or_id: str) -> str:
    """Accept a full Spotify URL or a bare track ID."""
    match = re.search(r"track/([A-Za-z0-9]+)", url_or_id)
    if match:
        return match.group(1)
    # bare 22-char ID
    if re.fullmatch(r"[A-Za-z0-9]{22}", url_or_id):
        return url_or_id
    raise ValueError(f"Cannot parse track ID from: {url_or_id!r}")


def fetch_track_info(sp: spotipy.Spotify, track_id: str) -> dict:
    """Return a flat dict with the metadata we care about."""
    t = sp.track(track_id)
    artists = ", ".join(a["name"] for a in t["artists"])
    album   = t["album"]["name"]
    title   = t["name"]

    # pick the largest image
    images = t["album"]["images"]
    cover_url = images[0]["url"] if images else None

    return {
        "title":     title,
        "artist":    artists,
        "album":     album,
        "cover_url": cover_url,
    }


def download_cover(url: str) -> bytes:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.content


# ─── AcoustID / MusicBrainz helpers ──────────────────────────────────────────

def _fetch_musicbrainz_cover(recording_id: str) -> bytes | None:
    """Try to find cover art for a MusicBrainz recording via its releases."""
    try:
        url = f"https://musicbrainz.org/ws/2/recording/{recording_id}"
        r = requests.get(url, params={"fmt": "json", "inc": "releases"},
                         headers={"User-Agent": MB_USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
        for release in data.get("releases", []):
            rid = release["id"]
            try:
                cr = requests.get(f"https://coverartarchive.org/release/{rid}/front",
                                  timeout=10)
                if cr.status_code == 200:
                    return cr.content
            except Exception:
                continue
    except Exception:
        pass
    return None


def fingerprint_and_lookup(audio_path: str, api_key: str = ACOUSTID_DEFAULT_KEY) -> dict:
    """
    Fingerprint an audio file via AcoustID, then fetch metadata + cover via MusicBrainz.
    Returns the same dict structure as fetch_track_info().
    """
    raw = acoustid.match(api_key, audio_path,
                         meta=["recordings", "releasegroups"], parse=False)
    if raw.get("status") != "ok":
        msg = raw.get("error", {}).get("message", "unknown error")
        if "invalid API key" in msg:
            msg += " — get a free key at https://acoustid.org/"
        raise ValueError(msg)

    results = raw.get("results", [])
    if not results:
        raise ValueError("No matching track found (AcoustID returned no results)")

    # Find best result with a recording
    best_result = None
    best_recording = None
    best_score = -1
    for result in results:
        score = result["score"]
        recordings = result.get("recordings", [])
        if recordings and score > best_score:
            best_result = result
            best_recording = recordings[0]
            best_score = score

    if not best_recording:
        raise ValueError("No matching track found (no recordings in AcoustID results)")

    recording_id = best_recording["id"]
    title = best_recording.get("title", "")
    artists = best_recording.get("artists", [])
    artist = ", ".join(a["name"] for a in artists) if artists else "Unknown Artist"

    # Album from first release group
    album = ""
    for rg in best_recording.get("releasegroups", []):
        album = rg.get("title", "")
        if album:
            break

    mb_cover = _fetch_musicbrainz_cover(recording_id)

    info = {
        "title":     title,
        "artist":    artist,
        "album":     album,
        "cover_url": None,
    }

    if mb_cover:
        info["cover_url"] = "__embedded__"
        info["cover_data"] = mb_cover

    print(f"[*] Match score: {best_score:.1%}")
    return info


# ─── Taggers ──────────────────────────────────────────────────────────────────

def tag_mp3(path: str, info: dict, cover: bytes | None):
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    tags["TIT2"] = TIT2(encoding=3, text=info["title"])
    tags["TPE1"] = TPE1(encoding=3, text=info["artist"])
    tags["TALB"] = TALB(encoding=3, text=info["album"])

    if cover:
        tags["APIC"] = APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,           # front cover
            desc="Cover",
            data=cover,
        )

    tags.save(path, v2_version=3)


def tag_m4a(path: str, info: dict, cover: bytes | None):
    audio = MP4(path)
    audio["\xa9nam"] = [info["title"]]
    audio["\xa9ART"] = [info["artist"]]
    audio["\xa9alb"] = [info["album"]]

    if cover:
        audio["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]

    audio.save()


def tag_opus(path: str, info: dict, cover: bytes | None):
    audio = OggOpus(path)
    audio["title"]  = [info["title"]]
    audio["artist"] = [info["artist"]]
    audio["album"]  = [info["album"]]

    if cover:
        pic = Picture()
        pic.type        = 3          # front cover
        pic.mime        = "image/jpeg"
        pic.desc        = "Cover"
        pic.data        = cover
        pic.width       = 0
        pic.height      = 0
        pic.depth       = 0
        pic.colors      = 0
        encoded = base64.b64encode(pic.write()).decode("ascii")
        audio["metadata_block_picture"] = [encoded]

    audio.save()


TAGGERS = {
    ".mp3":  tag_mp3,
    ".m4a":  tag_m4a,
    ".opus": tag_opus,
}


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Tag an audio file with Spotify metadata (title, artist, album, cover art).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Tag using environment variables for credentials (recommended):
  export SPOTIPY_CLIENT_ID=xxxx
  export SPOTIPY_CLIENT_SECRET=yyyy
  python3 spotify_tagger.py song.mp3 https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC

  # Pass credentials inline:
  python3 spotify_tagger.py song.m4a 4uLU6hMCjMI75M1A2tKUQC --id CLIENT_ID --secret CLIENT_SECRET

  # Skip cover art:
  python3 spotify_tagger.py song.opus TRACK_URL --no-cover

  # Auto-tag via AcoustID fingerprinting (no Spotify account needed):
  export ACOUSTID_API_KEY=your_key
  python3 spotify_tagger.py song.mp3 --acoustid

  # AcoustID with inline key:
  python3 spotify_tagger.py song.m4a --acoustid --acoustid-api-key YOUR_KEY
""",
    )
    p.add_argument("audio",  help="Path to the audio file (.mp3, .m4a, .opus)")
    p.add_argument("track", nargs="?", default=None,
                   help="Spotify track URL or bare track ID (not needed with --acoustid)")
    p.add_argument("--id",     dest="client_id",     default=os.getenv("SPOTIPY_CLIENT_ID"),
                   help="Spotify Client ID  (or set SPOTIPY_CLIENT_ID env var)")
    p.add_argument("--secret", dest="client_secret", default=os.getenv("SPOTIPY_CLIENT_SECRET"),
                   help="Spotify Client Secret (or set SPOTIPY_CLIENT_SECRET env var)")
    p.add_argument("--no-cover", action="store_true",
                   help="Skip embedding cover art")

    # AcoustID mode
    p.add_argument("--acoustid", action="store_true",
                   help="Use AcoustID audio fingerprinting instead of Spotify API")
    p.add_argument("--acoustid-api-key",
                   default=os.getenv("ACOUSTID_API_KEY", ACOUSTID_DEFAULT_KEY),
                   help="AcoustID API key (default: built-in, get your own at acoustid.org)")

    return p.parse_args()


def main():
    args = parse_args()

    # ── validate audio file ──
    if not os.path.isfile(args.audio):
        sys.exit(f"[error] File not found: {args.audio}")

    ext = os.path.splitext(args.audio)[1].lower()
    if ext not in TAGGERS:
        sys.exit(f"[error] Unsupported format '{ext}'. Supported: {', '.join(TAGGERS)}")

    # ── AcoustID / MusicBrainz mode ──
    if args.acoustid:
        print(f"[*] Fingerprinting {args.audio} …")
        try:
            info = fingerprint_and_lookup(args.audio, args.acoustid_api_key)
        except Exception as e:
            sys.exit(f"[error] AcoustID lookup failed: {e}")

        print(f"[*] Track  : {info['title']}")
        print(f"[*] Artist : {info['artist']}")
        print(f"[*] Album  : {info['album']}")

        cover_bytes = None
        if not args.no_cover and info.get("cover_data"):
            cover_bytes = info["cover_data"]
            print(f"[*] Cover  : {len(cover_bytes)//1024} KB (from MusicBrainz)")
        elif args.no_cover:
            print(f"[*] Cover  : skipped (--no-cover)")
        else:
            print(f"[warn] No cover art found on MusicBrainz.")

    # ── Spotify mode ──
    else:
        if not args.track:
            sys.exit("[error] A Spotify track URL/ID is required (or use --acoustid for auto-detection).")
        if not args.client_id or not args.client_secret:
            sys.exit(
                "[error] Spotify credentials missing.\n"
                "  Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET env vars, or use --id / --secret."
            )

        print(f"[*] Connecting to Spotify API …")
        try:
            sp = build_spotify_client(args.client_id, args.client_secret)
            track_id = extract_track_id(args.track)
            info = fetch_track_info(sp, track_id)
        except Exception as e:
            sys.exit(f"[error] Spotify fetch failed: {e}")

        print(f"[*] Track  : {info['title']}")
        print(f"[*] Artist : {info['artist']}")
        print(f"[*] Album  : {info['album']}")

        # ── cover art ──
        cover_bytes = None
        if not args.no_cover and info["cover_url"]:
            print(f"[*] Downloading cover art …")
            try:
                cover_bytes = download_cover(info["cover_url"])
                print(f"[*] Cover  : {len(cover_bytes)//1024} KB")
            except Exception as e:
                print(f"[warn] Could not download cover: {e}")
        elif args.no_cover:
            print(f"[*] Cover  : skipped (--no-cover)")
        else:
            print(f"[warn] No cover URL returned by Spotify.")

    # ── tag ──
    print(f"[*] Tagging {args.audio} …")
    try:
        TAGGERS[ext](args.audio, info, cover_bytes)
    except Exception as e:
        sys.exit(f"[error] Tagging failed: {e}")

    print(f"[✓] Done! {args.audio} has been tagged.")


if __name__ == "__main__":
    main()
