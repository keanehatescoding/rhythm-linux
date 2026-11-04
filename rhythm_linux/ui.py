"""GTK 4 user interface."""
from __future__ import annotations

from pathlib import Path

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .library import (AUDIO_EXTENSIONS, SORT_KEYS, Track, merge_tracks, read_cover,  # noqa: E402
                      read_track, scan_folder, sort_tracks)
from .player import Player  # noqa: E402
from .playlists import PlaylistStore  # noqa: E402
from .queue import REPEAT_ALL, REPEAT_OFF, REPEAT_ONE, PlaybackQueue  # noqa: E402
from .settings import Settings  # noqa: E402

LIBRARY_LABEL = "Library"
PLAY_ICON = "media-playback-start-symbolic"
PAUSE_ICON = "media-playback-pause-symbolic"


def _format_time(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _margins(widget, n=6):
    widget.set_margin_top(n)
    widget.set_margin_bottom(n)
    widget.set_margin_start(n)
    widget.set_margin_end(n)
    return widget


def _label(text: str, dim: bool = False) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    if dim:
        label.add_css_class("dim-label")
    return label


def _row(text: str, sublabel: str = "") -> Gtk.ListBoxRow:
    row = Gtk.ListBoxRow()
    box = _margins(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2), 6)
    box.append(_label(text))
    if sublabel:
        box.append(_label(sublabel, dim=True))
    row.set_child(box)
    return row


def _listbox_rows(listbox: Gtk.ListBox):
    index = 0
    while True:
        row = listbox.get_row_at_index(index)
        if row is None:
            return
        yield row
        index += 1


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, music_dir: Path, store: PlaylistStore,
                 settings: Settings):
        super().__init__(application=app, title="Rhythm", default_width=1000, default_height=640)
        self.music_dir = music_dir
        self.store = store
        self.settings = settings
        self.tracks: list[Track] = []          # what the library view shows
        self.session_tracks: list[Track] = []  # files dropped in this session
        self._scan_generation = 0
        self._populate_generation = 0
        self._pending_select: int | None = None
        self.queue = PlaybackQueue()   # order of the view that was last played from
        self.current_playlist: str | None = None
        self.player = Player(on_end_of_stream=self._play_next)

        header = Gtk.HeaderBar()
        open_btn = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Choose music folder")
        open_btn.connect("clicked", self._choose_folder)
        header.pack_start(open_btn)
        self.set_titlebar(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self._build_body())
        body.append(self._build_footer())
        self.set_child(body)

        self.connect("close-request", self._on_close)
        self.player.set_volume(self.settings.volume)
        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)
        GLib.timeout_add(500, self._tick)
        self.session_tracks = [read_track(p) for p in self.settings.extra_files if Path(p).is_file()]
        self.queue.repeat = self.settings.repeat
        self._update_repeat_button()
        self.queue.set_shuffle(self.settings.shuffle)
        self.shuffle_btn.set_active(self.settings.shuffle)
        keys = Gtk.EventControllerKey()
        # Capture phase: shortcuts run before a focused button or dropdown can
        # consume Space or letter keys. Text fields are still excluded in _on_key.
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.refresh_playlists()
        self.rescan()

    # ---- layout -----------------------------------------------------------

    def _build_body(self) -> Gtk.Paned:
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        paned.set_position(240)
        paned.set_shrink_start_child(False)

        side = _margins(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6), 6)
        self.sidebar = Gtk.ListBox()
        self.sidebar.add_css_class("navigation-sidebar")
        self.sidebar.connect("row-selected", self._on_sidebar_selected)
        side.append(Gtk.ScrolledWindow(vexpand=True, child=self.sidebar))

        self.new_playlist_entry = Gtk.Entry(placeholder_text="New playlist name, then Enter")
        self.new_playlist_entry.connect("activate", self._on_new_playlist)
        side.append(self.new_playlist_entry)

        self.delete_playlist_btn = Gtk.Button(label="Delete playlist", sensitive=False)
        self.delete_playlist_btn.connect("clicked", self._on_delete_playlist)
        side.append(self.delete_playlist_btn)
        paned.set_start_child(side)

        main = _margins(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6), 6)
        self.search = Gtk.Entry(placeholder_text="Search title, artist, album",
                                primary_icon_name="system-search-symbolic", hexpand=True)
        self.search.connect("changed", lambda *_: self.track_list.invalidate_filter())
        self.sort_dropdown = Gtk.DropDown.new_from_strings(list(SORT_KEYS))
        self.sort_dropdown.set_tooltip_text("Sort library by")
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_row.append(self.search)
        search_row.append(self.sort_dropdown)
        main.append(search_row)

        self.track_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.track_list.add_css_class("boxed-list")
        self.track_list.set_filter_func(self._filter_row)
        self.track_list.connect("row-activated", self._on_track_activated)
        main.append(Gtk.ScrolledWindow(vexpand=True, child=self.track_list))

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.target_dropdown = Gtk.DropDown(model=Gtk.StringList())
        self.add_to_btn = Gtk.Button(label="Add selected to playlist")
        self.add_to_btn.connect("clicked", self._on_add_to_playlist)
        self.remove_btn = Gtk.Button(label="Remove from this playlist", sensitive=False)
        self.remove_btn.connect("clicked", self._on_remove_from_playlist)
        self.move_up_btn = Gtk.Button(icon_name="go-up-symbolic", tooltip_text="Move up in playlist",
                                      sensitive=False)
        self.move_down_btn = Gtk.Button(icon_name="go-down-symbolic", tooltip_text="Move down in playlist",
                                        sensitive=False)
        self.move_up_btn.connect("clicked", lambda *_: self._on_move(-1))
        self.move_down_btn.connect("clicked", lambda *_: self._on_move(1))
        self.track_list.connect("row-selected", lambda *_: self._update_playlist_controls())
        for widget in (self.target_dropdown, self.add_to_btn, self.remove_btn,
                       self.move_up_btn, self.move_down_btn):
            actions.append(widget)
        main.append(actions)
        paned.set_end_child(main)
        return paned

    def _build_footer(self) -> Gtk.Box:
        bar = _margins(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6), 8)
        self.play_btn = Gtk.Button(icon_name=PLAY_ICON, tooltip_text="Play / pause")
        buttons = [
            (Gtk.Button(icon_name="media-skip-backward-symbolic", tooltip_text="Previous"),
             lambda *_: self._play_previous()),
            (self.play_btn, lambda *_: self._toggle_play()),
            (Gtk.Button(icon_name="media-skip-forward-symbolic", tooltip_text="Next"),
             lambda *_: self._play_next()),
            (Gtk.Button(icon_name="media-playback-stop-symbolic", tooltip_text="Stop"),
             lambda *_: self._stop()),
        ]
        for button, handler in buttons:
            button.connect("clicked", handler)
            bar.append(button)
        self.mute_btn = Gtk.ToggleButton(tooltip_text="Mute")
        self.mute_btn.connect("toggled", self._on_mute_toggled)
        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.01)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_size_request(120, -1)
        self.volume_scale.set_tooltip_text("Volume")
        self.volume_scale.set_value(self.settings.volume)
        self.volume_scale.connect("value-changed", self._on_volume_changed)
        bar.append(self.mute_btn)
        bar.append(self.volume_scale)
        self._update_volume_icon()
        self.shuffle_btn = Gtk.ToggleButton(icon_name="media-playlist-shuffle-symbolic",
                                            tooltip_text="Shuffle")
        self.shuffle_btn.connect("toggled", self._on_shuffle_toggled)
        self.repeat_btn = Gtk.Button()
        self.repeat_btn.connect("clicked", self._on_repeat_clicked)
        bar.append(self.shuffle_btn)
        bar.append(self.repeat_btn)
        self._update_repeat_button()
        self.art = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        self.art.set_pixel_size(48)
        self.now_playing = _label("Not playing")
        self.now_playing.set_hexpand(True)
        bar.append(self.art)
        self.status = _label("", dim=True)
        self.status.set_xalign(1)
        self.progress = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.001)
        self.progress.set_draw_value(False)
        self.progress.set_hexpand(True)
        self.progress.set_sensitive(False)
        self.progress.connect("change-value", self._on_progress_dragged)
        self.time_label = _label("0:00 / 0:00", dim=True)
        bar.append(self.now_playing)
        bar.append(self.progress)
        bar.append(self.time_label)
        bar.append(self.status)
        return bar

    # ---- library and playlists ---------------------------------------------

    def rescan(self) -> None:
        """Scan the music folder on a worker thread; the UI stays responsive."""
        self._scan_generation += 1
        generation, folder = self._scan_generation, self.music_dir
        self.status.set_label(f"Scanning {folder}\u2026")
        worker = threading.Thread(target=self._scan_worker, args=(generation, folder), daemon=True)
        worker.start()

    def _scan_worker(self, generation: int, folder: Path) -> None:
        # Runs off the main thread: reads files only, touches no widgets.
        tracks = scan_folder(folder)
        GLib.idle_add(self._scan_finished, generation, folder, tracks)

    def _scan_finished(self, generation: int, folder: Path, scanned: list[Track]) -> bool:
        if generation != self._scan_generation:
            return False  # a newer scan has started; drop this result
        self.tracks = merge_tracks(scanned, self.session_tracks)
        self.status.set_label(f"{len(scanned)} tracks in {folder}")
        self.populate_track_list()
        return False  # run once

    def _sort_key(self) -> str:
        item = self.sort_dropdown.get_selected_item()
        return item.get_string() if item is not None else "Artist"

    def _on_sort_changed(self, *_args) -> None:
        self.populate_track_list()

    def _view_tracks(self) -> list[Track]:
        if self.current_playlist is None:
            return sort_tracks(self.tracks, self._sort_key())
        by_path = {t.path: t for t in self.tracks}
        return [by_path.get(p) or read_track(p) for p in self.store.tracks(self.current_playlist)]

    def populate_track_list(self) -> None:
        """Rebuild the track list in small batches so large libraries don't freeze the window."""
        self._populate_generation += 1
        self.track_list.remove_all()
        self.delete_playlist_btn.set_sensitive(self.current_playlist is not None)
        self._append_rows(self._populate_generation, self._view_tracks(), 0)

    def _update_playlist_controls(self) -> None:
        row = self.track_list.get_selected_row()
        in_playlist = self.current_playlist is not None
        has_sel = in_playlist and row is not None
        count = len(self.store.tracks(self.current_playlist)) if in_playlist else 0
        index = row.get_index() if has_sel else -1
        self.remove_btn.set_sensitive(has_sel)
        self.move_up_btn.set_sensitive(has_sel and index > 0)
        self.move_down_btn.set_sensitive(has_sel and index < count - 1)

    def _on_move(self, delta: int) -> None:
        row = self.track_list.get_selected_row()
        if row is None or self.current_playlist is None:
            return
        self._pending_select = self.store.move_track(self.current_playlist, row.get_index(), delta)
        self.populate_track_list()

    ROW_BATCH = 250

    def _append_rows(self, generation: int, tracks: list[Track], start: int) -> bool:
        if generation != self._populate_generation:
            return False  # a newer list has been requested
        for track in tracks[start:start + self.ROW_BATCH]:
            row = _row(track.display_text, track.album)
            row.track = track
            self.track_list.append(row)
        self.track_list.invalidate_filter()
        if start + self.ROW_BATCH < len(tracks):
            GLib.idle_add(self._append_rows, generation, tracks, start + self.ROW_BATCH)
        else:
            self._finish_populate()
        return False

    def _finish_populate(self) -> None:
        if self._pending_select is not None:
            row = self.track_list.get_row_at_index(self._pending_select)
            self._pending_select = None
            if row is not None:
                self.track_list.select_row(row)
        self._update_playlist_controls()

    def refresh_playlists(self) -> None:
        names = self.store.names()
        if self.current_playlist not in names:
            self.current_playlist = None

        self.sidebar.remove_all()
        library_row = _row(LIBRARY_LABEL)
        library_row.playlist_name = None
        self.sidebar.append(library_row)
        for name in names:
            row = _row(name)
            row.playlist_name = name
            self.sidebar.append(row)
        self.sidebar.select_row(self._sidebar_row_for(self.current_playlist) or library_row)

        model = self.target_dropdown.get_model()
        model.splice(0, model.get_n_items(), names)
        if names:
            self.target_dropdown.set_selected(0)
        self.add_to_btn.set_sensitive(bool(names))

    def _sidebar_row_for(self, name: str | None):
        for row in _listbox_rows(self.sidebar):
            if getattr(row, "playlist_name", None) == name:
                return row
        return None

    def _matches_search(self, track: Track) -> bool:
        query = self.search.get_text().strip().lower()
        return not query or query in track.search_text

    def _filter_row(self, row: Gtk.ListBoxRow) -> bool:
        if not hasattr(row, "track"):
            return True
        return self._matches_search(row.track)

    def _on_sidebar_selected(self, _box, row) -> None:
        if row is None:
            return
        self.current_playlist = getattr(row, "playlist_name", None)
        self.populate_track_list()

    def _on_new_playlist(self, entry: Gtk.Entry) -> None:
        name = entry.get_text().strip()
        try:
            self.store.create(name)
        except ValueError as exc:
            self.status.set_label(str(exc))
            return
        entry.set_text("")
        self.current_playlist = name
        self.refresh_playlists()
        self.populate_track_list()

    def _on_delete_playlist(self, _btn) -> None:
        if self.current_playlist is None:
            return
        self.store.delete(self.current_playlist)
        self.current_playlist = None
        self.refresh_playlists()
        self.populate_track_list()

    def _selected_track(self) -> Track | None:
        row = self.track_list.get_selected_row()
        return getattr(row, "track", None)

    def _on_add_to_playlist(self, _btn) -> None:
        track = self._selected_track()
        item = self.target_dropdown.get_selected_item()
        if track is None or item is None:
            self.status.set_label("Select a track and a playlist first")
            return
        name = item.get_string()
        self.store.add_track(name, track.path)
        self.status.set_label(f"Added to {name}")

    def _on_remove_from_playlist(self, _btn) -> None:
        row = self.track_list.get_selected_row()
        if row is None or self.current_playlist is None:
            return
        self.store.remove_track(self.current_playlist, row.get_index())
        self.populate_track_list()

    # ---- playback ----------------------------------------------------------

    def _on_track_activated(self, _listbox, row) -> None:
        view = [t for t in self._view_tracks() if self._matches_search(t)]
        self.queue.set_tracks(view, start=row.track)
        self._play_track(self.queue.current())

    def _play_track(self, track: Track | None) -> None:
        if track is None:
            return
        self.player.play_file(track.path)
        if self.player.error:
            self.now_playing.set_label(f"Could not play {track.title}: {self.player.error}")
            self.play_btn.set_icon_name(PLAY_ICON)
            return
        self.now_playing.set_label(track.display_text)
        self._show_art(track.path)
        self.play_btn.set_icon_name(PAUSE_ICON)

    def _show_art(self, path: str) -> None:
        data = read_cover(path)
        texture = None
        if data:
            try:
                texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
            except GLib.Error:
                texture = None
        if texture is not None:
            self.art.set_from_paintable(texture)
        else:
            self.art.set_from_icon_name("audio-x-generic-symbolic")

    def _toggle_play(self) -> None:
        if not self.player.has_media:
            row = self.track_list.get_selected_row()
            if row is not None:
                self._on_track_activated(self.track_list, row)
            return
        if self.player.is_playing:
            self.player.pause()
            self.play_btn.set_icon_name(PLAY_ICON)
        else:
            self.player.resume()
            self.play_btn.set_icon_name(PAUSE_ICON)

    def _play_next(self) -> None:
        track = self.queue.next()
        if track is None:
            self._stop()
        else:
            self._play_track(track)

    def _play_previous(self) -> None:
        self._play_track(self.queue.previous())

    def _on_volume_changed(self, scale: Gtk.Scale) -> None:
        level = scale.get_value()
        self.player.set_volume(level)
        if self.mute_btn.get_active():
            self.mute_btn.set_active(False)  # moving the slider unmutes
        self.settings.volume = level
        self._update_volume_icon()

    def _on_mute_toggled(self, button: Gtk.ToggleButton) -> None:
        self.player.set_muted(button.get_active())
        self._update_volume_icon()

    def _update_volume_icon(self) -> None:
        if self.mute_btn.get_active() or self.volume_scale.get_value() == 0:
            icon, tip = "audio-volume-muted-symbolic", "Unmute"
        else:
            level = self.volume_scale.get_value()
            icon = ("audio-volume-high-symbolic" if level > 0.66
                    else "audio-volume-medium-symbolic" if level > 0.33
                    else "audio-volume-low-symbolic")
            tip = "Mute"
        self.mute_btn.set_icon_name(icon)
        self.mute_btn.set_tooltip_text(tip)

    def _on_shuffle_toggled(self, button: Gtk.ToggleButton) -> None:
        self.queue.set_shuffle(button.get_active())
        self.settings.shuffle = button.get_active()

    def _on_repeat_clicked(self, _button) -> None:
        self.queue.cycle_repeat()
        self.settings.repeat = self.queue.repeat
        self._update_repeat_button()

    def _update_repeat_button(self) -> None:
        mode = self.queue.repeat
        if mode == REPEAT_ONE:
            self.repeat_btn.set_icon_name("media-playlist-repeat-song-symbolic")
            self.repeat_btn.set_tooltip_text("Repeat: this track")
        elif mode == REPEAT_ALL:
            self.repeat_btn.set_icon_name("media-playlist-repeat-symbolic")
            self.repeat_btn.set_tooltip_text("Repeat: all")
        else:
            self.repeat_btn.set_icon_name("media-playlist-repeat-symbolic")
            self.repeat_btn.set_tooltip_text("Repeat: off")
        self.repeat_btn.set_opacity(1.0 if mode != REPEAT_OFF else 0.5)

    def _stop(self) -> None:
        self.player.stop()
        self.play_btn.set_icon_name(PLAY_ICON)
        self.now_playing.set_label("Not playing")
        self.art.set_from_icon_name("audio-x-generic-symbolic")
        self._reset_progress()

    def _tick(self) -> bool:
        if self.player.has_media:
            pos = self.player.position_seconds()
            dur = self.player.duration_seconds()
            if dur > 0:
                self.progress.set_sensitive(True)
                self.progress.set_value(min(pos / dur, 1.0))
            self.time_label.set_label(f"{_format_time(pos)} / {_format_time(dur)}")
        return True  # keep the timer running

    def _on_progress_dragged(self, _scale, _kind, value) -> bool:
        dur = self.player.duration_seconds()
        if dur > 0:
            self.player.seek_seconds(value * dur)
        return False

    def _reset_progress(self) -> None:
        self.progress.set_value(0)
        self.progress.set_sensitive(False)
        self.time_label.set_label("0:00 / 0:00")

    def _on_close(self, *_args) -> bool:
        self.player.stop()
        return False  # let the window close

    # ---- keyboard ----------------------------------------------------------

    def _on_key(self, _controller, keyval, _keycode, state) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search.grab_focus()
            return True
        if ctrl and keyval == Gdk.KEY_Right:
            self._play_next()
            return True
        if ctrl and keyval == Gdk.KEY_Left:
            self._play_previous()
            return True
        if isinstance(self.get_focus(), (Gtk.Entry, Gtk.Text)):
            return False  # let text fields receive typing
        if keyval == Gdk.KEY_space:
            self._toggle_play()
        elif keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self.shuffle_btn.set_active(not self.shuffle_btn.get_active())
        elif keyval in (Gdk.KEY_r, Gdk.KEY_R):
            self.repeat_btn.emit("clicked")
        elif keyval in (Gdk.KEY_m, Gdk.KEY_M):
            self.mute_btn.set_active(not self.mute_btn.get_active())
        else:
            return False
        return True

    # ---- drag and drop -----------------------------------------------------

    def _on_drop(self, _target, value, _x, _y) -> bool:
        paths = [Path(f.get_path()) for f in value.get_files() if f.get_path()]
        folders = [p for p in paths if p.is_dir()]
        if folders:
            # A dropped folder becomes the music folder (and is remembered).
            self.music_dir = folders[0]
            self.settings.music_dir = str(self.music_dir)
            self.session_tracks = []
            self.settings.extra_files = []
            self.rescan()
            return True
        known = {t.path for t in self.tracks}
        added = [read_track(p) for p in paths
                 if p.suffix.lower() in AUDIO_EXTENSIONS and str(p) not in known]
        if not added:
            self.status.set_label("Drop a music folder or audio files")
            return False
        self.session_tracks.extend(added)
        self.settings.extra_files = [t.path for t in self.session_tracks]
        self.tracks.extend(added)
        self.status.set_label(f"Added {len(added)} file(s) for this session")
        self.populate_track_list()
        return True

    # ---- folder choice -----------------------------------------------------

    def _choose_folder(self, _btn) -> None:
        dialog = Gtk.FileDialog(title="Choose music folder")
        dialog.select_folder(self, None, self._on_folder_chosen)

    def _on_folder_chosen(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return  # cancelled
        self.music_dir = Path(folder.get_path())
        self.settings.music_dir = str(self.music_dir)
        self.rescan()


class RhythmApp(Gtk.Application):
    def __init__(self, music_dir: Path | None, store_path: Path, settings_path: Path):
        super().__init__(application_id="local.rhythm.Linux",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = Settings(settings_path)
        self.settings.load()
        self.music_dir = music_dir or Path(self.settings.music_dir or Path.home() / "Music")
        self.store = PlaylistStore(store_path)
        self.store.load()
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: Gtk.Application) -> None:
        MainWindow(app, self.music_dir, self.store, self.settings).present()
