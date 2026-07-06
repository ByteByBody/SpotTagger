#!/usr/bin/env python3
"""
spotify_tagger_app.py — GTK3 GUI
Tag audio files with Spotify metadata and drop them into your
Spotify local-files folder so they appear in the Spotify client.
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Gio

import os, sys, re, threading, subprocess, json, base64, shutil
import urllib.request, urllib.parse
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
TAGGER      = SCRIPT_DIR / "spotify_tagger.py"
VENV_PY     = SCRIPT_DIR / ".venv" / "bin" / "python3"
PYTHON      = str(VENV_PY) if VENV_PY.exists() else sys.executable
SUPPORTED   = {".mp3", ".m4a", ".opus"}

# Default Spotify local files folder (user can change in UI)
DEFAULT_LOCAL  = Path.home() / "Music" / "Spotify Local"
CONFIG_DIR     = Path.home() / ".config" / "spotify-tagger"
CONFIG_PATH    = CONFIG_DIR / "config.json"

CSS = b"""
window { background-color: #0e0e10; }
.sidebar {
    background-color: #141416;
    border-right: 1px solid #2a2a2e;
    padding: 20px 16px;
}
.main-area { background-color: #0e0e10; padding: 20px; }
.drop-zone {
    background-color: #141416;
    border: 2px dashed #2a2a2e;
    border-radius: 12px;
    padding: 24px 16px;
}
.drop-zone.dragover {
    border-color: #1db954;
    background-color: #0e1f13;
}
.drop-zone.has-file {
    border-style: solid;
    border-color: #1db954;
}
.section-label { font-size: 10px; font-weight: 700; color: #4a4a58; }
.drop-hint { font-size: 12px; color: #5a5a6a; }
.filename-label {
    font-family: monospace;
    font-size: 11px;
    color: #1db954;
    background-color: rgba(29,185,84,0.1);
    border-radius: 6px;
    padding: 4px 8px;
}
.fmt-badge {
    font-size: 10px;
    font-weight: 600;
    color: #4a4a58;
    background-color: #1e1e22;
    border-radius: 4px;
    padding: 2px 7px;
    margin: 2px;
}
.cred-input {
    background-color: #1a1a1f;
    color: #e8e8ec;
    border: 1px solid #2a2a2e;
    border-radius: 8px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 12px;
}
.cred-input:focus { border-color: #1db954; }
.url-entry {
    background-color: #1a1a1f;
    color: #e8e8ec;
    border: 1px solid #2a2a2e;
    border-radius: 8px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 12px;
}
.url-entry:focus { border-color: #1db954; }
.folder-entry {
    background-color: #1a1a1f;
    color: #e8e8ec;
    border: 1px solid #2a2a2e;
    border-radius: 8px 0 0 8px;
    padding: 8px 12px;
    font-family: monospace;
    font-size: 11px;
}
.folder-entry:focus { border-color: #1db954; }
.meta-card {
    background-color: #141416;
    border: 1px solid #2a2a2e;
    border-radius: 12px;
    padding: 16px;
}
.meta-label { font-size: 10px; font-weight: 700; color: #4a4a58; }
.meta-value { font-family: monospace; font-size: 12px; color: #e8e8ec; }
.meta-value.empty { color: #3a3a48; font-family: sans-serif; }
.cover-placeholder {
    background-color: #1e1e22;
    border: 1px solid #2a2a2e;
    border-radius: 10px;
}
.tag-btn {
    background-color: #1db954;
    color: #000000;
    font-weight: 700;
    font-size: 14px;
    border: none;
    border-radius: 8px;
    padding: 12px 24px;
}
.tag-btn:hover { background-color: #1ed760; }
.tag-btn:disabled { background-color: #1e1e22; color: #3a3a48; }
.status-bar {
    background-color: #141416;
    border: 1px solid #2a2a2e;
    border-radius: 8px;
    padding: 8px 12px;
}
.status-ok { background-color: rgba(29,185,84,0.08); border-color: rgba(29,185,84,0.3); }
.status-err { background-color: rgba(220,53,69,0.08); border-color: rgba(220,53,69,0.3); }
.status-text { font-family: monospace; font-size: 12px; color: #5a5a6a; }
.status-text.ok  { color: #1db954; }
.status-text.err { color: #dc3545; }
.no-cover-check { color: #5a5a6a; font-size: 12px; }
.local-toggle { color: #5a5a6a; font-size: 12px; }
.local-panel {
    background-color: #0e1f13;
    border: 1px solid rgba(29,185,84,0.25);
    border-radius: 8px;
    padding: 12px;
}
.local-hint { font-size: 11px; color: #3a5a3a; }
headerbar {
    background-color: #0e0e10;
    border-bottom: 1px solid #1e1e22;
    box-shadow: none;
    min-height: 48px;
}
headerbar .title { font-size: 13px; font-weight: 600; color: #e8e8ec; }
"""

def apply_css(widget, *classes):
    ctx = widget.get_style_context()
    for c in classes:
        ctx.add_class(c)

def remove_css(widget, *classes):
    ctx = widget.get_style_context()
    for c in classes:
        ctx.remove_class(c)


class SpotifyTaggerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.abdo.spotifytagger",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = TaggerWindow(application=self)
        win.show_all()
        # local panel starts hidden
        win.local_panel.set_visible(win.local_toggle.get_active())


class TaggerWindow(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title="Spotify Tagger", **kwargs)
        self.set_default_size(860, 560)
        self.set_resizable(True)
        self.audio_path       = None
        self.meta             = None
        self.cover_bytes      = None
        self._fetch_timeout_id = None
        self._build_header()
        self._build_ui()
        self._apply_styles()
        self._load_config()

    # ── Header ────────────────────────────────────────────────────
    def _build_header(self):
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = "Spotify Tagger"
        self.set_titlebar(hb)

    # ── UI ────────────────────────────────────────────────────────
    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(root)

        # ── SIDEBAR ───────────────────────────────────────────────
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        sidebar.set_size_request(230, -1)
        apply_css(sidebar, "sidebar")
        root.pack_start(sidebar, False, False, 0)

        # Mode selector
        mode_lbl = Gtk.Label(label="SOURCE")
        mode_lbl.set_halign(Gtk.Align.START)
        apply_css(mode_lbl, "section-label")
        sidebar.pack_start(mode_lbl, False, False, 0)

        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.append("spotify", "Spotify API")
        self.mode_combo.append("acoustid", "Auto (AcoustID)")
        self.mode_combo.set_active(0)
        self.mode_combo.connect("changed", self._on_mode_changed)
        sidebar.pack_start(self.mode_combo, False, False, 0)

        # Drop zone
        lbl = Gtk.Label(label="AUDIO FILE")
        lbl.set_halign(Gtk.Align.START)
        apply_css(lbl, "section-label")
        sidebar.pack_start(lbl, False, False, 0)

        self.drop_box = Gtk.EventBox()
        apply_css(self.drop_box, "drop-zone")

        drop_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        drop_inner.set_halign(Gtk.Align.CENTER)
        drop_inner.set_valign(Gtk.Align.CENTER)
        drop_inner.set_margin_top(8)
        drop_inner.set_margin_bottom(8)

        self.drop_icon = Gtk.Label()
        self.drop_icon.set_markup('<span font="24" foreground="#4a4a58">♫</span>')
        drop_inner.pack_start(self.drop_icon, False, False, 0)

        strong = Gtk.Label()
        strong.set_markup('<span font="13" foreground="#e8e8ec" font_weight="bold">Drop file here</span>')
        weak = Gtk.Label(label="or click to browse")
        apply_css(weak, "drop-hint")
        drop_inner.pack_start(strong, False, False, 0)
        drop_inner.pack_start(weak,   False, False, 0)

        badges = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        badges.set_halign(Gtk.Align.CENTER)
        for fmt in ["mp3", "m4a", "opus"]:
            b = Gtk.Label(label=fmt)
            apply_css(b, "fmt-badge")
            badges.pack_start(b, False, False, 0)
        drop_inner.pack_start(badges, False, False, 0)

        self.drop_box.add(drop_inner)
        sidebar.pack_start(self.drop_box, False, False, 0)

        self.fname_label = Gtk.Label(label="")
        self.fname_label.set_line_wrap(True)
        self.fname_label.set_max_width_chars(26)
        self.fname_label.set_halign(Gtk.Align.START)
        apply_css(self.fname_label, "filename-label")
        self.fname_label.set_visible(False)
        sidebar.pack_start(self.fname_label, False, False, 0)

        # Credentials (hidden in AcoustID mode)
        self.creds_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cl = Gtk.Label(label="SPOTIFY CREDENTIALS")
        cl.set_halign(Gtk.Align.START)
        apply_css(cl, "section-label")
        self.creds_box.pack_start(cl, False, False, 0)

        self.cid_entry = Gtk.Entry()
        self.cid_entry.set_placeholder_text("Client ID")
        apply_css(self.cid_entry, "cred-input")
        self.creds_box.pack_start(self.cid_entry, False, False, 0)

        self.csec_entry = Gtk.Entry()
        self.csec_entry.set_placeholder_text("Client secret")
        self.csec_entry.set_visibility(False)
        apply_css(self.csec_entry, "cred-input")
        self.creds_box.pack_start(self.csec_entry, False, False, 0)

        cred_hint = Gtk.Label()
        cred_hint.set_markup('<span font="11" foreground="#4a4a58">developer.spotify.com</span>')
        cred_hint.set_halign(Gtk.Align.START)
        self.creds_box.pack_start(cred_hint, False, False, 0)
        sidebar.pack_start(self.creds_box, False, False, 0)

        # AcoustID hint (hidden in Spotify mode)
        # AcoustID section (hidden in Spotify mode)
        self.acoustid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.acoustid_box.set_visible(False)

        self.acoustid_key_entry = Gtk.Entry()
        self.acoustid_key_entry.set_placeholder_text("AcoustID API key")
        s = self.acoustid_key_entry.get_style_context()
        s.add_class("cred-input")
        self.acoustid_key_entry.set_text(os.getenv("ACOUSTID_API_KEY", ""))
        self.acoustid_box.pack_start(self.acoustid_key_entry, False, False, 0)

        acoustid_hint = Gtk.Label()
        acoustid_hint.set_markup(
            '<span font="11" foreground="#5a5a6a">'
            'Free key at acoustid.org — or set ACOUSTID_API_KEY env var.</span>'
        )
        acoustid_hint.set_halign(Gtk.Align.START)
        acoustid_hint.set_line_wrap(True)
        self.acoustid_box.pack_start(acoustid_hint, False, False, 0)
        sidebar.pack_start(self.acoustid_box, False, False, 0)

        # ── MAIN AREA ─────────────────────────────────────────────
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        apply_css(main, "main-area")
        root.pack_start(main, True, True, 0)

        # Track URL row (hidden in AcoustID mode)
        self.url_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        url_lbl = Gtk.Label(label="SPOTIFY TRACK URL OR ID")
        url_lbl.set_halign(Gtk.Align.START)
        apply_css(url_lbl, "section-label")
        self.url_box.pack_start(url_lbl, False, False, 0)

        url_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("https://open.spotify.com/track/…")
        apply_css(self.url_entry, "url-entry")
        self.url_entry.connect("changed", self._on_url_changed)
        url_row.pack_start(self.url_entry, True, True, 0)

        self.fetch_btn = Gtk.Button(label="Fetch")
        self.fetch_btn.connect("clicked", self._on_fetch)
        url_row.pack_start(self.fetch_btn, False, False, 0)
        self.url_box.pack_start(url_row, False, False, 0)
        main.pack_start(self.url_box, False, False, 0)

        # Meta card
        meta_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        apply_css(meta_card, "meta-card")

        # Cover
        self.cover_box = Gtk.Box()
        self.cover_box.set_size_request(100, 100)
        apply_css(self.cover_box, "cover-placeholder")
        self.cover_icon = Gtk.Label()
        self.cover_icon.set_markup('<span font="28" foreground="#2a2a2e">♫</span>')
        self.cover_icon.set_halign(Gtk.Align.CENTER)
        self.cover_icon.set_valign(Gtk.Align.CENTER)
        self.cover_box.pack_start(self.cover_icon, True, True, 0)
        self.cover_image = Gtk.Image()
        self.cover_image.set_visible(False)
        self.cover_box.pack_start(self.cover_image, True, True, 0)
        meta_card.pack_start(self.cover_box, False, False, 0)

        fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        fields_box.set_valign(Gtk.Align.CENTER)
        meta_card.pack_start(fields_box, True, True, 0)
        self.m_title  = self._make_meta_row(fields_box, "TITLE")
        self.m_artist = self._make_meta_row(fields_box, "ARTIST")
        self.m_album  = self._make_meta_row(fields_box, "ALBUM")
        main.pack_start(meta_card, True, True, 0)

        # Options row
        opts = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.no_cover = Gtk.CheckButton(label="Skip cover art")
        apply_css(self.no_cover, "no-cover-check")
        opts.pack_start(self.no_cover, False, False, 0)

        self.local_toggle = Gtk.CheckButton(label="Add to Spotify local files")
        self.local_toggle.set_active(True)
        apply_css(self.local_toggle, "local-toggle")
        self.local_toggle.connect("toggled", self._on_local_toggled)
        opts.pack_start(self.local_toggle, False, False, 0)
        main.pack_start(opts, False, False, 0)

        # Local files panel
        self.local_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        apply_css(self.local_panel, "local-panel")

        folder_lbl = Gtk.Label(label="LOCAL FILES FOLDER")
        folder_lbl.set_halign(Gtk.Align.START)
        apply_css(folder_lbl, "section-label")
        self.local_panel.pack_start(folder_lbl, False, False, 0)

        folder_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.folder_entry = Gtk.Entry()
        self.folder_entry.set_text(str(DEFAULT_LOCAL))
        apply_css(self.folder_entry, "folder-entry")
        folder_row.pack_start(self.folder_entry, True, True, 0)

        browse_btn = Gtk.Button(label="…")
        browse_btn.set_tooltip_text("Browse for folder")
        browse_btn.connect("clicked", self._on_browse_folder)
        folder_row.pack_start(browse_btn, False, False, 0)
        self.local_panel.pack_start(folder_row, False, False, 0)

        hint = Gtk.Label()
        hint.set_markup(
            '<span font="11" foreground="#3a5a3a">'
            'Tagged file will be copied here. In Spotify: Settings → Local Files → Add source → point to this folder.'
            '</span>'
        )
        hint.set_line_wrap(True)
        hint.set_halign(Gtk.Align.START)
        self.local_panel.pack_start(hint, False, False, 0)
        main.pack_start(self.local_panel, False, False, 0)

        # Status
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        apply_css(self.status_box, "status-bar")
        self.status_lbl = Gtk.Label(label="Ready — drop a file and paste a Spotify URL")
        self.status_lbl.set_halign(Gtk.Align.START)
        apply_css(self.status_lbl, "status-text")
        self.status_box.pack_start(self.status_lbl, True, True, 0)
        main.pack_start(self.status_box, False, False, 0)

        # Tag button
        self.tag_btn = Gtk.Button(label="Tag & Save")
        self.tag_btn.set_sensitive(False)
        self.tag_btn.connect("clicked", self._on_tag)
        apply_css(self.tag_btn, "tag-btn")
        main.pack_start(self.tag_btn, False, False, 0)

        # ── Drag-and-drop ─────────────────────────────────────────
        self.drop_box.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
            Gdk.DragAction.COPY,
        )
        self.drop_box.connect("drag-data-received", self._on_dnd_received)
        self.drop_box.connect("drag-motion",        self._on_dnd_motion)
        self.drop_box.connect("drag-leave",         self._on_dnd_leave)
        self.drop_box.connect("button-press-event", self._on_drop_click)

    def _make_meta_row(self, parent, label_text):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(Gtk.Align.START)
        apply_css(lbl, "meta-label")
        val = Gtk.Label(label="—")
        val.set_halign(Gtk.Align.START)
        val.set_ellipsize(3)
        apply_css(val, "meta-value", "empty")
        box.pack_start(lbl, False, False, 0)
        box.pack_start(val, False, False, 0)
        parent.pack_start(box, False, False, 0)
        return val

    def _apply_styles(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ── DnD ──────────────────────────────────────────────────────
    def _on_dnd_motion(self, widget, ctx, x, y, t):
        apply_css(widget, "dragover")
        return True

    def _on_dnd_leave(self, widget, ctx, t):
        remove_css(widget, "dragover")

    def _on_dnd_received(self, widget, ctx, x, y, data, info, t):
        remove_css(widget, "dragover")
        uris = data.get_uris()
        if uris:
            path = Gio.File.new_for_uri(uris[0]).get_path()
            if path:
                self._set_file(path)

    def _on_drop_click(self, widget, event):
        dialog = Gtk.FileChooserDialog(
            title="Choose audio file", parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,   Gtk.ResponseType.OK,
        )
        f = Gtk.FileFilter()
        f.set_name("Audio files (mp3, m4a, opus)")
        for pat in ["*.mp3", "*.m4a", "*.opus"]:
            f.add_pattern(pat)
        dialog.add_filter(f)
        if dialog.run() == Gtk.ResponseType.OK:
            self._set_file(dialog.get_filename())
        dialog.destroy()

    def _set_file(self, path):
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED:
            self._set_status(f"Unsupported format '{ext}' — use mp3, m4a, or opus", "err")
            return
        self.audio_path = path
        self.meta = None
        self.cover_bytes = None
        remove_css(self.drop_box, "dragover")
        apply_css(self.drop_box, "has-file")
        self.drop_icon.set_markup('<span font="24" foreground="#1db954">✓</span>')
        self.fname_label.set_text(Path(path).name)
        self.fname_label.set_visible(True)
        if self._is_acoustid():
            self._set_status(f"Loaded: {Path(path).name} — click Tag & Save to auto-detect via AcoustID")
        else:
            self._set_status(f"Loaded: {Path(path).name} — paste a Spotify URL and fetch")
            self._reset_meta_display()
        self._check_ready()

    def _on_local_toggled(self, btn):
        self.local_panel.set_visible(btn.get_active())
        label = "Tag & Save to Local Files" if btn.get_active() else "Tag & Save"
        self.tag_btn.set_label(label)

    def _on_browse_folder(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Choose local files folder", parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,   Gtk.ResponseType.OK,
        )
        if dialog.run() == Gtk.ResponseType.OK:
            self.folder_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def _is_acoustid(self):
        return self.mode_combo.get_active_id() == "acoustid"

    def _on_mode_changed(self, combo):
        is_acoustid = self._is_acoustid()
        self.creds_box.set_visible(not is_acoustid)
        self.acoustid_box.set_visible(is_acoustid)
        self.url_box.set_visible(not is_acoustid)
        self.meta = None
        self.cover_bytes = None
        self._reset_meta_display()

        if is_acoustid:
            self._set_status("AcoustID mode — drop an audio file and click Tag & Save")
        else:
            self._set_status("Spotify mode — drop a file, paste a URL, and fetch")

        if self.audio_path:
            self._set_status(f"Loaded: {Path(self.audio_path).name}")
        self._check_ready()

    # ── Config persistence ───────────────────────────────────────
    def _load_config(self):
        try:
            data = json.loads(CONFIG_PATH.read_text())
            self.cid_entry.set_text(data.get("spotify_client_id", ""))
            self.csec_entry.set_text(data.get("spotify_client_secret", ""))
            self.acoustid_key_entry.set_text(data.get("acoustid_api_key", ""))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "spotify_client_id":     self.cid_entry.get_text().strip(),
            "spotify_client_secret": self.csec_entry.get_text().strip(),
            "acoustid_api_key":      self.acoustid_key_entry.get_text().strip(),
        }
        CONFIG_PATH.write_text(json.dumps(data, indent=2))

    # ── Auto-fetch on URL paste ─────────────────────────────────
    def _on_url_changed(self, entry):
        if self._fetch_timeout_id is not None:
            GLib.source_remove(self._fetch_timeout_id)
            self._fetch_timeout_id = None
        url = entry.get_text().strip()
        if not url:
            return
        m = re.search(r"track/([A-Za-z0-9]{22})", url)
        is_valid = bool(m) or bool(re.fullmatch(r"[A-Za-z0-9]{22}", url))
        if is_valid:
            track_id = m.group(1) if m else url
            self._fetch_timeout_id = GLib.timeout_add(400, self._auto_fetch, track_id)

    def _auto_fetch(self, track_id):
        self._fetch_timeout_id = None
        cid  = self.cid_entry.get_text().strip()
        csec = self.csec_entry.get_text().strip()
        if not cid or not csec:
            self._set_status("Enter your Spotify Client ID and Secret", "err")
            return False
        self.fetch_btn.set_sensitive(False)
        self._set_status("Auto-fetching metadata from Spotify…")
        threading.Thread(target=self._fetch_worker, args=(cid, csec, track_id), daemon=True).start()
        return False

    # ── Fetch ─────────────────────────────────────────────────────
    def _on_fetch(self, btn):
        url  = self.url_entry.get_text().strip()
        cid  = self.cid_entry.get_text().strip()
        csec = self.csec_entry.get_text().strip()
        if not url:
            self._set_status("Paste a Spotify track URL or ID", "err"); return
        if not cid or not csec:
            self._set_status("Enter your Spotify Client ID and Secret", "err"); return
        m = re.search(r"track/([A-Za-z0-9]{22})", url)
        if not m and re.fullmatch(r"[A-Za-z0-9]{22}", url):
            track_id = url
        elif m:
            track_id = m.group(1)
        else:
            self._set_status("Cannot parse track ID from that URL", "err"); return
        self.fetch_btn.set_sensitive(False)
        self._set_status("Fetching metadata from Spotify…")
        threading.Thread(target=self._fetch_worker, args=(cid, csec, track_id), daemon=True).start()

    def _fetch_worker(self, cid, csec, track_id):
        try:
            creds = base64.b64encode(f"{cid}:{csec}".encode()).decode()
            req = urllib.request.Request(
                "https://accounts.spotify.com/api/token",
                data=b"grant_type=client_credentials",
                headers={
                    "Authorization": f"Basic {creds}",
                    "Content-Type":  "application/x-www-form-urlencoded",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                tok = json.loads(r.read())["access_token"]

            req2 = urllib.request.Request(
                f"https://api.spotify.com/v1/tracks/{track_id}",
                headers={"Authorization": f"Bearer {tok}"}
            )
            with urllib.request.urlopen(req2, timeout=10) as r:
                t = json.loads(r.read())

            meta = {
                "title":     t["name"],
                "artist":    ", ".join(a["name"] for a in t["artists"]),
                "album":     t["album"]["name"],
                "cover_url": t["album"]["images"][0]["url"] if t["album"]["images"] else None,
            }
            cover_bytes = None
            if meta["cover_url"]:
                with urllib.request.urlopen(meta["cover_url"], timeout=10) as r:
                    cover_bytes = r.read()

            GLib.idle_add(self._on_fetch_done, meta, cover_bytes)
        except Exception as e:
            GLib.idle_add(self._on_fetch_error, str(e))

    def _on_fetch_done(self, meta, cover_bytes):
        self.meta         = meta
        self.cover_bytes  = cover_bytes
        self.fetch_btn.set_sensitive(True)
        self._save_config()
        for widget, key in [(self.m_title, "title"), (self.m_artist, "artist"), (self.m_album, "album")]:
            widget.set_text(meta[key])
            remove_css(widget, "empty")
        if cover_bytes:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(cover_bytes)
            loader.close()
            pb = loader.get_pixbuf().scale_simple(100, 100, GdkPixbuf.InterpType.BILINEAR)
            self.cover_image.set_from_pixbuf(pb)
            self.cover_icon.set_visible(False)
            self.cover_image.set_visible(True)
        self._set_status("Metadata ready — click Tag & Save", "ok")
        self._check_ready()
        return False

    def _on_fetch_error(self, msg):
        self.fetch_btn.set_sensitive(True)
        self._set_status(f"Fetch error: {msg}", "err")
        return False

    def _reset_meta_display(self):
        for w in [self.m_title, self.m_artist, self.m_album]:
            w.set_text("—")
            apply_css(w, "empty")
        self.cover_icon.set_visible(True)
        self.cover_image.set_visible(False)

    # ── Tag & Save ────────────────────────────────────────────────
    def _check_ready(self):
        if self._is_acoustid():
            self.tag_btn.set_sensitive(bool(self.audio_path))
        else:
            self.tag_btn.set_sensitive(bool(self.audio_path and self.meta))

    def _on_tag(self, btn):
        if not self.audio_path:
            return
        to_local = self.local_toggle.get_active()
        local_dir = Path(self.folder_entry.get_text().strip()) if to_local else None

        if self._is_acoustid():
            cmd = [PYTHON, str(TAGGER), self.audio_path, "--acoustid"]
            ak = self.acoustid_key_entry.get_text().strip()
            if ak:
                cmd += ["--acoustid-api-key", ak]
            env = os.environ.copy()
        else:
            if not self.meta:
                return
            cid   = self.cid_entry.get_text().strip()
            csec  = self.csec_entry.get_text().strip()
            url   = self.url_entry.get_text().strip()
            env = os.environ.copy()
            env["SPOTIPY_CLIENT_ID"]     = cid
            env["SPOTIPY_CLIENT_SECRET"] = csec
            cmd = [PYTHON, str(TAGGER), self.audio_path, url]

        if self.no_cover.get_active():
            cmd.append("--no-cover")

        btn.set_sensitive(False)
        self._set_status("Tagging file…")
        threading.Thread(
            target=self._tag_worker,
            args=(cmd, env, self.audio_path, local_dir),
            daemon=True,
        ).start()

    def _tag_worker(self, cmd, env, src_path, local_dir):
        try:
            timeout = 120 if "--acoustid" in cmd else 30
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip()
                GLib.idle_add(self._on_tag_done, False, err, None)
                return

            dest = None
            if local_dir:
                local_dir.mkdir(parents=True, exist_ok=True)
                dest = local_dir / Path(src_path).name
                shutil.copy2(src_path, dest)

            GLib.idle_add(self._on_tag_done, True, "", dest)
        except Exception as e:
            GLib.idle_add(self._on_tag_done, False, str(e), None)

    def _on_tag_done(self, ok, err, dest):
        self.tag_btn.set_sensitive(True)
        self._save_config()
        if ok:
            name = Path(self.audio_path).name
            if dest:
                msg = f"Done! '{name}' tagged and copied to local files folder."
            else:
                msg = f"Done! '{name}' has been tagged."
            self._set_status(msg, "ok")
            if dest:
                self._show_spotify_hint(dest)
        else:
            self._set_status(f"Error: {err}", "err")
        return False

    def _show_spotify_hint(self, dest):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="File added to local files folder",
        )
        dialog.format_secondary_text(
            f"Saved to:\n{dest}\n\n"
            "To make it appear in Spotify:\n"
            "1. Open Spotify\n"
            "2. Settings → Local Files\n"
            "3. Add source → select the folder above\n"
            "4. Your song will appear under Local Files in Your Library"
        )
        dialog.run()
        dialog.destroy()

    # ── Status ────────────────────────────────────────────────────
    def _set_status(self, msg, kind=None):
        ctx_box = self.status_box.get_style_context()
        ctx_lbl = self.status_lbl.get_style_context()
        for c in ["status-ok", "status-err"]:
            ctx_box.remove_class(c)
        for c in ["ok", "err"]:
            ctx_lbl.remove_class(c)
        self.status_lbl.set_text(msg)
        if kind == "ok":
            ctx_box.add_class("status-ok")
            ctx_lbl.add_class("ok")
        elif kind == "err":
            ctx_box.add_class("status-err")
            ctx_lbl.add_class("err")


if __name__ == "__main__":
    app = SpotifyTaggerApp()
    sys.exit(app.run(sys.argv))
