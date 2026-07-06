#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
if [ -f "$VENV/bin/python3" ]; then
    exec "$VENV/bin/python3" "$SCRIPT_DIR/spotify_tagger_app.py" "$@"
else
    exec python3 "$SCRIPT_DIR/spotify_tagger_app.py" "$@"
fi
