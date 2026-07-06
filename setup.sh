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
    echo "  # Spotify mode (requires API credentials):"
    echo "    $SCRIPT_DIR/stag song.mp3 https://open.spotify.com/track/..."
    echo ""
    echo "  # AcoustID mode (no Spotify account needed):"
    echo "    export ACOUSTID_API_KEY=your_key"
    echo "    $SCRIPT_DIR/stag song.mp3 --acoustid"
    echo ""
    echo "  Note: AcoustID requires libchromaprint:"
    echo "    sudo apt install libchromaprint-dev   # Debian/Ubuntu"
    echo "    sudo pacman -S chromaprint            # Arch"
    echo ""
    echo "  Get a free AcoustID API key at: https://acoustid.org/"

# Create the wrapper launcher
LAUNCHER="$SCRIPT_DIR/stag"
cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
exec "\$SCRIPT_DIR/.venv/bin/python3" "\$SCRIPT_DIR/spotify_tagger.py" "\$@"
EOF
chmod +x "$LAUNCHER"
echo "[✓] Launcher created: $LAUNCHER"
