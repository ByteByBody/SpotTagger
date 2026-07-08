#!/usr/bin/env bash
# setup.sh — create a venv and install spotify_tagger dependencies
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "[*] Creating virtual environment at $VENV_DIR …"
python3 -m venv "$VENV_DIR"

echo "[*] Installing dependencies …"
"$VENV_DIR/bin/pip" install --quiet mutagen spotipy requests pyacoustid

echo ""
echo "[✓] Setup complete. Run the tagger with:"
    echo ""
    echo "  # Spotify mode:"
    echo "    $SCRIPT_DIR/stag song.mp3 https://open.spotify.com/track/... --id CLIENT_ID --secret CLIENT_SECRET"
    echo ""
    echo "  # MusicBrainz Search mode (no API keys):"
    echo "    $SCRIPT_DIR/stag song.mp3 "Track -- Artist" --musicbrainz"
    echo ""
    echo "  # Local Player mode (no API keys, reads from running Spotify):"
    echo "    $SCRIPT_DIR/stag song.mp3 --from-player"
    echo ""
    echo "  # AcoustID fingerprinting (requires free API key from acoustid.org):"
    echo "    export ACOUSTID_API_KEY=your_key"
    echo "    $SCRIPT_DIR/stag song.mp3 --acoustid"
    echo ""
    echo "  # GUI:"
    echo "    $SCRIPT_DIR/launch.sh"
    echo ""
    echo "  Note: AcoustID requires libchromaprint:"
    echo "    sudo apt install libchromaprint-dev   # Debian/Ubuntu"
    echo "    sudo pacman -S chromaprint            # Arch"
    echo ""
    echo "  Note: Local Player mode requires playerctl:"
    echo "    sudo apt install playerctl            # Debian/Ubuntu"
    echo "    sudo pacman -S playerctl              # Arch"
    echo ""
    echo "  Get API keys:"
    echo "    Spotify: https://developer.spotify.com"
    echo "    AcoustID: https://acoustid.org/"

# Create the wrapper launcher
LAUNCHER="$SCRIPT_DIR/stag"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
exec "\$SCRIPT_DIR/.venv/bin/python3" "\$SCRIPT_DIR/spotify_tagger.py" "\$@"
EOF
chmod +x "$LAUNCHER"
echo "[✓] Launcher created: $LAUNCHER"

# Install .desktop file with correct absolute path
DESKTOP_SRC="$SCRIPT_DIR/spotify-tagger.desktop"
DESKTOP_DST="$HOME/.local/share/applications/spotify-tagger.desktop"
mkdir -p "$HOME/.local/share/applications"
sed "s|LAUNCH_SCRIPT_PATH|$SCRIPT_DIR/launch.sh|g" "$DESKTOP_SRC" > "$DESKTOP_DST"
chmod 644 "$DESKTOP_DST"
echo "[✓] Desktop entry installed: $DESKTOP_DST"
