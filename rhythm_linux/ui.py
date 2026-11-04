"""GTK 4 user interface."""
from __future__ import annotations

import dataclasses
import logging
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from .library import (AUDIO_EXTENSIONS, SORT_KEYS, Track, group_tracks, merge_tracks,  # noqa: E402
                      read_cover, read_track, scan_folder, sort_tracks)
from .player import Player  # noqa: E402
from .playlists import PlaylistStore  # noqa: E402
from .equalizer import PRESET_NAMES, gains_for  # noqa: E402
from . import iphone  # noqa: E402
from .export import copy_tracks  # noqa: E402
from . import phone_send  # noqa: E402
from .phone_tools import missing_text, startup_notice  # noqa: E402

CROSSFADE_OPTIONS = [(0, "Crossfade off"), (3, "Crossfade 3 s"), (6, "Crossfade 6 s"), (10, "Crossfade 10 s")]
from .queue import REPEAT_ALL, REPEAT_OFF, REPEAT_ONE, PlaybackQueue  # noqa: E402
from .settings import Settings  # noqa: E402
from .stats import FILTERS, MAX_RATING, STATS_SORTS, TrackStats, filter_by_stats, sort_by_stats  # noqa: E402

LIBRARY_LABEL = "Library"
BROWSE_VIEWS = (("Albums", "album"), ("Artists", "artist"), ("Up Next", "queue"))  # under Library
IPHONE_LABEL = "iPhone (read-only)"
IPHONE_BROWSE = "iphone"
SEARCH_DELAY_MS = 250  # wait this long after typing stops before filtering the library
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


RATING_LABELS = ["No rating"] + ["★" * n for n in range(1, MAX_RATING + 1)]


def _listbox_rows(listbox: Gtk.ListBox):
    index = 0
    while True:
        row = listbox.get_row_at_index(index)
        if row is None:
            return
        yield row
        index += 1


def _row(text: str, sublabel: str | None = None) -> Gtk.ListBoxRow:
    """A list row. Pass sublabel=None for no second line; "" keeps an empty second line."""
    row = Gtk.ListBoxRow()
    box = _margins(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2), 6)
    box.append(_label(text))
    row.sub_label = None
    if sublabel is not None:
        row.sub_label = _label(sublabel, dim=True)
        box.append(row.sub_label)
    row.set_child(box)
    return row


class TrackRow(GObject.Object):
    """One entry in the track list: the text shown, plus the object it stands for.

    Optional attributes (track, iphone_file, group, group_name, queue_offset) are set only
    on the kinds of rows that have them, so hasattr() tells the kinds apart.
    """

    def __init__(self, title: str, summary: str | None = None, **attrs):
        super().__init__()
        self.title = title
        self.summary = summary  # the second line; None means no second line
        for name, value in attrs.items():
            setattr(self, name, value)


def _track_factory() -> Gtk.SignalListItemFactory:
    factory = Gtk.SignalListItemFactory()
    factory.connect("setup", _on_row_setup)
    factory.connect("bind", _on_row_bind)
    return factory


def _on_row_setup(_factory, list_item) -> None:
    box = _margins(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2), 6)
    box.append(_label(""))
    box.append(_label("", dim=True))
    list_item.set_child(box)


def _on_row_bind(_factory, list_item) -> None:
    row = list_item.get_item()
    box = list_item.get_child()
    title, sub = box.get_first_child(), box.get_last_child()
    title.set_label(row.title)
    sub.set_label(row.summary or "")
    sub.set_visible(row.summary is not None)


log = logging.getLogger("rhythm_linux")

_phone_released = threading.Event()  # set when the app is closing
_phone_thread: threading.Thread | None = None  # the worker that may be mounting right now


def release_phone() -> None:
    """Unmount the read-only iPhone view if it is mounted. Never raises."""
    _phone_released.set()
    try:
        # Let an in-flight mount finish first, so it cannot outlive the app.
        if _phone_thread is not None and _phone_thread.is_alive():
            _phone_thread.join(timeout=20)
        iphone.unmount(iphone.default_mountpoint())
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        # A stuck or missing phone must not block quitting; say what happened on stderr.
        log.warning("Could not unmount the iPhone view: %s", exc)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, music_dir: Path, store: PlaylistStore,
                 settings: Settings, stats: TrackStats):
        super().__init__(application=app, title="Rhythm", default_width=1000, default_height=640)
        self.music_dir = music_dir
        self.store = store
        self.settings = settings
        self.stats = stats
        self.tracks: list[Track] = []          # what the library view shows
        self.session_tracks: list[Track] = []  # files dropped in this session
        self._scan_generation = 0
        self._populate_generation = 0
        self._pending_select: int | None = None
        self.queue = PlaybackQueue()   # order of the view that was last played from
        self.current_playlist: str | None = None
        self.browse_by: str | None = None  # "album" or "artist" when browsing groups
        self.player = Player(on_end_of_stream=self._play_next, on_gapless=self._on_gapless_advance)

        header = Gtk.HeaderBar()
        open_btn = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Choose music folder")
        open_btn.connect("clicked", self._choose_folder)
        header.pack_start(open_btn)
        # The equalizer is a global setting, so it lives in the header bar rather than the crowded footer.
        self.eq_dropdown = Gtk.DropDown.new_from_strings(list(PRESET_NAMES))
        self.eq_dropdown.set_tooltip_text("Equalizer preset")
        self.eq_dropdown.set_selected(PRESET_NAMES.index(self.settings.equalizer)
                                      if self.settings.equalizer in PRESET_NAMES else 0)
        self.eq_dropdown.connect("notify::selected", self._on_eq_chosen)
        header.pack_end(self.eq_dropdown)
        # Crossfade is also global, so it sits in the header bar next to the equalizer.
        self.fade_dropdown = Gtk.DropDown.new_from_strings([label for _secs, label in CROSSFADE_OPTIONS])
        self.fade_dropdown.set_tooltip_text("Crossfade between tracks")
        self.fade_dropdown.set_selected(self._crossfade_index(self.settings.crossfade))
        self.fade_dropdown.connect("notify::selected", self._on_fade_chosen)
        header.pack_end(self.fade_dropdown)
        self.set_titlebar(header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self._build_body())
        body.append(self._build_footer())
        self.set_child(body)

        self.connect("close-request", self._on_close)
        self.player.set_volume(self.settings.volume)
        self.player.set_equalizer(gains_for(self.settings.equalizer))
        self.player.set_crossfade(self.settings.crossfade)
        drop =Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
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

        self.rename_playlist_entry = Gtk.Entry(placeholder_text="Rename selected playlist, then Enter",
                                               sensitive=False)
        self.rename_playlist_entry.connect("activate", self._on_rename_playlist)
        side.append(self.rename_playlist_entry)

        self.delete_playlist_btn = Gtk.Button(label="Delete playlist", sensitive=False)
        self.delete_playlist_btn.connect("clicked", self._on_delete_playlist)
        side.append(self.delete_playlist_btn)

        self.export_playlist_btn = Gtk.Button(label="Export playlist…", sensitive=False)
        self.export_playlist_btn.connect("clicked", self._on_export_playlist)
        side.append(self.export_playlist_btn)

        import_playlist_btn = Gtk.Button(label="Import playlist…")
        import_playlist_btn.connect("clicked", self._on_import_playlist)
        side.append(import_playlist_btn)
        paned.set_start_child(side)

        main = _margins(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6), 6)
        self.search = Gtk.Entry(placeholder_text="Search title, artist, album",
                                primary_icon_name="system-search-symbolic", hexpand=True)
        self._search_timer = 0
        self.search.connect("changed", self._on_search_changed)
        self.sort_dropdown = Gtk.DropDown.new_from_strings(list(SORT_KEYS) + list(STATS_SORTS))
        self.sort_dropdown.set_tooltip_text("Sort library by")
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        self.filter_dropdown = Gtk.DropDown.new_from_strings(list(FILTERS))
        self.filter_dropdown.set_tooltip_text("Show only tracks matching")
        self.filter_dropdown.connect("notify::selected", self._on_filter_changed)
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_row.append(self.search)
        search_row.append(self.filter_dropdown)
        search_row.append(self.sort_dropdown)
        main.append(search_row)

        # Only the rows on screen are built, so search and sort stay quick on a large library.
        self.track_store = Gio.ListStore.new(TrackRow)
        self._track_filter = Gtk.CustomFilter.new(self._filter_row)
        self._track_filtered = Gtk.FilterListModel.new(self.track_store, self._track_filter)
        self.track_selection = Gtk.SingleSelection.new(self._track_filtered)
        self.track_selection.set_autoselect(False)
        self.track_selection.set_can_unselect(True)
        self.track_list = Gtk.ListView(model=self.track_selection, factory=_track_factory())
        self.track_list.set_show_separators(True)
        self.track_list.connect("activate", self._on_list_activated)
        main.append(Gtk.ScrolledWindow(vexpand=True, child=self.track_list))

        # A wrapping row so the buttons drop to a second line in a narrow window
        # instead of running past the right edge.
        actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False,
                              column_spacing=6, row_spacing=6,
                              min_children_per_line=1, max_children_per_line=12)
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
        self.rating_dropdown = Gtk.DropDown.new_from_strings(RATING_LABELS)
        self.rating_dropdown.set_tooltip_text("Rate the selected track")
        self.rating_dropdown.set_sensitive(False)
        self._syncing_rating = False  # True while we set the dropdown from code
        self.rating_dropdown.connect("notify::selected", self._on_rating_chosen)
        self.export_shown_btn = Gtk.Button(label="Export shown to folder…",
                                           tooltip_text="Copy the tracks in this list (after search and filter)")
        self.export_shown_btn.connect("clicked", self._on_export_shown)
        self.send_shown_btn = Gtk.Button(label="Send shown to phone",
                                         tooltip_text="Send the tracks in this list to the paired phone with KDE Connect")
        self.send_shown_btn.connect("clicked", self._on_send_shown)
        self.track_selection.connect("notify::selected-item", lambda *_: self._update_playlist_controls())
        for widget in (self.target_dropdown, self.add_to_btn, self.remove_btn,
                       self.move_up_btn, self.move_down_btn, self.rating_dropdown,
                       self.export_shown_btn, self.send_shown_btn):
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
        summary = f"{len(scanned)} tracks in {folder}"
        notice = startup_notice()  # phone features that cannot run, if any
        self.status.set_label(f"{summary}. {notice}" if notice else summary)
        self.populate_track_list()
        return False  # run once

    def _sort_key(self) -> str:
        item = self.sort_dropdown.get_selected_item()
        return item.get_string() if item is not None else "Artist"

    def _on_sort_changed(self, *_args) -> None:
        self.populate_track_list()

    def _filter_choice(self) -> str:
        item = self.filter_dropdown.get_selected_item()
        return item.get_string() if item is not None else "All tracks"

    def _on_filter_changed(self, *_args) -> None:
        self.populate_track_list()

    def _view_tracks(self) -> list[Track]:
        return filter_by_stats(self._sorted_view_tracks(), self.stats, self._filter_choice())

    def _sorted_view_tracks(self) -> list[Track]:
        if self.current_playlist is None:
            by = self._sort_key()
            if by in STATS_SORTS:
                return sort_by_stats(self.tracks, self.stats, by)
            return sort_tracks(self.tracks, by)
        by_path = {t.path: t for t in self.tracks}
        return [by_path.get(p) or read_track(p) for p in self.store.tracks(self.current_playlist)]

    def populate_track_list(self) -> None:
        """Rebuild the track list in small batches so large libraries don't freeze the window."""
        self._prepare_next()  # the queue may have changed; keep the gapless hand-off in step
        self._populate_generation += 1
        self.track_store.remove_all()
        self.delete_playlist_btn.set_sensitive(self.current_playlist is not None)
        self.rename_playlist_entry.set_sensitive(self.current_playlist is not None)
        self.export_playlist_btn.set_sensitive(self.current_playlist is not None)
        if self.browse_by == "queue":
            self._append_rows(self._populate_generation, self.queue.upcoming(), 0, queue_mode=True)
            return
        if self.browse_by == IPHONE_BROWSE:
            self._start_iphone_read()
            return
        if self.browse_by is not None:
            self._append_group_rows()
            return
        self._append_rows(self._populate_generation, self._view_tracks(), 0)

    def _start_iphone_read(self) -> None:
        """Mount the phone read-only on a worker thread and list its audio files."""
        missing = iphone.tools_missing()
        if missing:
            self.status.set_label(missing_text("iPhone browsing", missing))
            return
        self._iphone_generation = getattr(self, "_iphone_generation", 0) + 1
        generation = self._iphone_generation
        self.status.set_label("Reading iPhone…")
        global _phone_thread
        _phone_thread = threading.Thread(target=self._iphone_worker, args=(generation,), daemon=True)
        _phone_thread.start()

    def _iphone_worker(self, generation: int) -> None:
        # Off the main thread: talks to the phone and reads file names only.
        try:
            device = iphone.connected_device()
            if device is None:
                result = ("error", "No iPhone found. Plug it in, unlock it and tap Trust.")
            else:
                mountpoint = iphone.default_mountpoint()
                iphone.mount_readonly(mountpoint)
                if _phone_released.is_set():  # the app closed while we were mounting
                    release_phone()
                    return
                files = iphone.list_audio_files(mountpoint)
                result = ("ok", (device.name, device.udid, mountpoint, files))
        except Exception as exc:
            # Broad on purpose: this thread must always report back, or the view stays on
            # "Reading iPhone". The full traceback goes to stderr.
            log.exception("iPhone read failed")
            result = ("error", f"iPhone read failed: {exc}")
        GLib.idle_add(self._iphone_finished, generation, result)

    def _iphone_finished(self, generation: int, result) -> bool:
        if generation != self._iphone_generation or self.browse_by != IPHONE_BROWSE:
            return False  # the user moved on; drop this result
        kind, payload = result
        self.track_store.remove_all()
        if kind == "error":
            self.status.set_label(payload)
            return False
        name, udid, mountpoint, files = payload
        self.status.set_label(f"{name}: {len(files)} audio files (read-only)")
        self.track_store.splice(self.track_store.get_n_items(), 0, [
            TrackRow(path.name, str(path.parent.relative_to(mountpoint)), iphone_file=path,
                     iphone_key=iphone.play_key(udid, mountpoint, path))
            for path in files])
        return False

    def _append_group_rows(self) -> None:
        """One row per album or artist. Activating a row plays every track in it."""
        rows = []
        for name, tracks in group_tracks(self.tracks, self.browse_by):
            count = f"{len(tracks)} track" + ("" if len(tracks) == 1 else "s")
            rows.append(TrackRow(name, count, group_name=name, group=tracks))
        self.track_store.splice(self.track_store.get_n_items(), 0, rows)  # the filter model filters new rows itself
        self._update_playlist_controls()

    def _update_playlist_controls(self) -> None:
        row = self._selected_row()
        if self.browse_by == "queue":
            self._update_queue_controls(row)
            self._sync_rating_control()
            return
        self.remove_btn.set_label("Remove from this playlist")
        self.move_up_btn.set_tooltip_text("Move up in playlist")
        self.move_down_btn.set_tooltip_text("Move down in playlist")
        in_playlist = self.current_playlist is not None
        has_sel = in_playlist and row is not None
        count = len(self.store.tracks(self.current_playlist)) if in_playlist else 0
        index = self._store_index(row) if has_sel else -1
        self.remove_btn.set_sensitive(has_sel)
        self.move_up_btn.set_sensitive(has_sel and index > 0)
        self.move_down_btn.set_sensitive(has_sel and index < count - 1)
        self._sync_rating_control()

    def _update_queue_controls(self, row) -> None:
        """Remove and Move buttons act on Up Next while that view is open."""
        offset = getattr(row, "queue_offset", None) if row is not None else None
        count = len(self.queue.upcoming())
        self.remove_btn.set_label("Remove from Up Next")
        self.move_up_btn.set_tooltip_text("Move up in Up Next")
        self.move_down_btn.set_tooltip_text("Move down in Up Next")
        self.remove_btn.set_sensitive(offset is not None)
        self.move_up_btn.set_sensitive(offset is not None and offset > 0)
        self.move_down_btn.set_sensitive(offset is not None and offset < count - 1)

    def _sync_rating_control(self) -> None:
        track = self._selected_track()
        self._syncing_rating = True
        self.rating_dropdown.set_sensitive(track is not None)
        self.rating_dropdown.set_selected(self.stats.rating(track.play_key) if track else 0)
        self._syncing_rating = False

    def _on_rating_chosen(self, *_args) -> None:
        if self._syncing_rating:
            return
        track = self._selected_track()
        stars = self.rating_dropdown.get_selected()
        if track is None or stars > MAX_RATING:  # an invalid position means no choice
            return
        self.stats.set_rating(track.play_key, stars)
        self._refresh_row_summary(track.path)
        self._rebuild_if_filtered()

    def _track_summary(self, track: Track) -> str:
        parts = [track.album] if track.album else []
        rating = self.stats.rating(track.play_key)
        if rating:
            parts.append("★" * rating + "☆" * (MAX_RATING - rating))
        plays = self.stats.plays(track.play_key)
        if plays:
            parts.append(f"{plays} play" + ("" if plays == 1 else "s"))
        return " · ".join(parts)

    def _rebuild_if_filtered(self) -> None:
        """A play or a rating can change which tracks a filter keeps. Rebuild the list when one is active.

        Deferred to an idle callback so the list is not rebuilt inside the row's own activation handler.
        """
        if self.browse_by is None and self._filter_choice() != "All tracks":
            GLib.idle_add(self._rebuild_filtered_list)

    def _rebuild_filtered_list(self) -> bool:
        self.populate_track_list()
        return False  # run once

    def _refresh_row_summary(self, track_path: str) -> None:
        for position, row in enumerate(self._store_rows()):
            track = getattr(row, "track", None)
            if track is not None and track.path == track_path and row.summary is not None:
                row.summary = self._track_summary(track)
                self.track_store.items_changed(position, 1, 1)  # makes the widget redraw its labels

    def _on_move(self, delta: int) -> None:
        row = self._selected_row()
        if row is None:
            return
        if self.browse_by == "queue":
            offset = getattr(row, "queue_offset", None)
            if offset is not None and self.queue.move_upcoming(offset, delta):
                self._pending_select = offset + delta  # Up Next rows start at offset 0
                self.populate_track_list()
            return
        if self.current_playlist is None:
            return
        self._pending_select = self.store.move_track(self.current_playlist, self._store_index(row), delta)
        self.populate_track_list()

    ROW_BATCH = 250

    def _append_rows(self, generation: int, tracks: list[Track], start: int,
                     queue_mode: bool = False) -> bool:
        if generation != self._populate_generation:
            return False  # a newer list has been requested
        batch = []
        for offset, track in enumerate(tracks[start:start + self.ROW_BATCH], start):
            attrs = {"track": track}
            if queue_mode:
                attrs["queue_offset"] = offset  # places after the current track; used to jump
            batch.append(TrackRow(track.display_text, self._track_summary(track), **attrs))
        self.track_store.splice(self.track_store.get_n_items(), 0, batch)  # the filter model filters new rows itself
        if start + self.ROW_BATCH < len(tracks):
            GLib.idle_add(self._append_rows, generation, tracks, start + self.ROW_BATCH, queue_mode)
        else:
            self._finish_populate()
        return False

    def _finish_populate(self) -> None:
        if self._pending_select is not None:
            rows = self._store_rows()
            row = rows[self._pending_select] if 0 <= self._pending_select < len(rows) else None
            self._pending_select = None
            if row is not None:
                self._select_row(row)
        self._update_playlist_controls()

    def refresh_playlists(self) -> None:
        names = self.store.names()
        if self.current_playlist not in names:
            self.current_playlist = None

        self.sidebar.remove_all()
        library_row = _row(LIBRARY_LABEL)
        library_row.playlist_name = None
        library_row.browse_by = None
        self.sidebar.append(library_row)
        for label, browse in BROWSE_VIEWS:
            row = _row(label)
            row.playlist_name = None
            row.browse_by = browse
            self.sidebar.append(row)
        iphone_row = _row(IPHONE_LABEL)
        iphone_row.playlist_name = None
        iphone_row.browse_by = IPHONE_BROWSE
        self.sidebar.append(iphone_row)
        for name in names:
            row = _row(name)
            row.playlist_name = name
            row.browse_by = None
            self.sidebar.append(row)
        selected = self._sidebar_row_for(self.current_playlist, self.browse_by)
        self.sidebar.select_row(selected or library_row)

        model = self.target_dropdown.get_model()
        model.splice(0, model.get_n_items(), names)
        if names:
            self.target_dropdown.set_selected(0)
        self.add_to_btn.set_sensitive(bool(names))

    def _sidebar_row_for(self, name: str | None, browse: str | None = None):
        for row in _listbox_rows(self.sidebar):
            if (getattr(row, "playlist_name", None) == name
                    and getattr(row, "browse_by", None) == browse):
                return row
        return None

    def _query_matches(self, text: str) -> bool:
        query = self.search.get_text().strip().lower()
        return not query or query in text

    def _matches_search(self, track: Track) -> bool:
        return self._query_matches(track.search_text)

    def _on_search_changed(self, _entry) -> None:
        # Re-filtering hides and shows every row widget, which freezes the window for a
        # moment on a large library. Wait until typing pauses so that happens once.
        if self._search_timer:
            GLib.source_remove(self._search_timer)
        self._search_timer = GLib.timeout_add(SEARCH_DELAY_MS, self._apply_search)

    def _apply_search(self) -> bool:
        self._search_timer = 0
        self._track_filter.changed(Gtk.FilterChange.DIFFERENT)
        return False

    def _filter_row(self, row: TrackRow) -> bool:
        if hasattr(row, "track"):
            return self._matches_search(row.track)
        if hasattr(row, "iphone_file"):
            return self._query_matches(row.iphone_file.name.lower())
        if hasattr(row, "group_name"):
            return self._query_matches(row.group_name.lower())
        return True

    def _on_sidebar_selected(self, _box, row) -> None:
        if row is None:
            return
        self.current_playlist = getattr(row, "playlist_name", None)
        self.browse_by = getattr(row, "browse_by", None)
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

    def _on_rename_playlist(self, entry: Gtk.Entry) -> None:
        if self.current_playlist is None:
            return
        new_name = entry.get_text().strip()
        try:
            self.store.rename(self.current_playlist, new_name)
        except ValueError as exc:
            self.status.set_label(str(exc))
            return
        entry.set_text("")
        self.current_playlist = new_name
        self.refresh_playlists()
        self.populate_track_list()

    def _shown_track_paths(self) -> list[Path]:
        """Files for the tracks currently visible in the list (search and filter applied)."""
        paths: list[Path] = []
        for row in self._visible_rows():
            if hasattr(row, "track"):
                paths.append(Path(row.track.path))
            elif hasattr(row, "iphone_file"):
                paths.append(row.iphone_file)
        return paths

    def _on_export_shown(self, _btn) -> None:
        paths = self._shown_track_paths()
        if not paths:
            self.status.set_label("Nothing to export in this list")
            return
        dialog = Gtk.FileDialog(title="Export to folder")
        dialog.select_folder(self, None, lambda d, r: self._on_export_folder_chosen(d, r, paths))

    def _on_send_shown(self, _btn) -> None:
        paths = self._shown_track_paths()
        if not paths:
            self.status.set_label("Nothing to send in this list")
            return
        self.status.set_label("Looking for a paired phone…")
        threading.Thread(target=self._send_worker, args=(paths,), daemon=True).start()

    def _send_worker(self, paths: list[Path]) -> None:
        # Off the main thread: runs kdeconnect-cli, touches no widgets.
        if not phone_send.available():
            GLib.idle_add(self._send_finished, None, missing_text("KDE Connect sending", ["kdeconnect-cli"]))
            return
        try:
            ids = phone_send.paired_device_ids()
        except Exception as exc:
            # Broad on purpose: this thread must always report back. Traceback goes to stderr.
            log.exception("KDE Connect lookup failed")
            GLib.idle_add(self._send_finished, None, f"KDE Connect error: {exc}")
            return
        if not ids:
            GLib.idle_add(self._send_finished, None, "No paired phone. Pair it in KDE Connect first.")
            return
        result = phone_send.send_files(ids[0], paths)
        GLib.idle_add(self._send_finished, result, None)

    def _send_finished(self, result, error) -> bool:
        if error is not None:
            self.status.set_label(error)
            return False
        total = len(result.sent) + len(result.failed)
        message = f"Sent {len(result.sent)} of {total} to phone"
        if result.failed:
            source, reason = result.failed[0]
            message += f"; {len(result.failed)} failed (e.g. {source.name}: {reason})"
        self.status.set_label(message)
        return False

    def _on_export_folder_chosen(self, dialog: Gtk.FileDialog, result, paths: list[Path]) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return  # cancelled
        self.status.set_label(f"Exporting {len(paths)} tracks…")
        threading.Thread(target=self._export_worker, args=(paths, Path(folder.get_path())),
                         daemon=True).start()

    def _export_worker(self, paths: list[Path], folder: Path) -> None:
        # Off the main thread: copies files only, touches no widgets.
        GLib.idle_add(self._export_finished, folder, copy_tracks(paths, folder))

    def _export_finished(self, folder: Path, result) -> bool:
        message = f"Exported {len(result.copied)} of {len(result.copied) + len(result.failed)} to {folder}"
        if result.failed:
            first_source, reason = result.failed[0]
            message += f"; {len(result.failed)} failed (e.g. {first_source.name}: {reason})"
        self.status.set_label(message)
        return False

    def _on_export_playlist(self, _btn) -> None:
        name = self.current_playlist
        if name is None:
            return
        dialog = Gtk.FileDialog(title="Export playlist")
        dialog.set_initial_name(f"{name}.m3u")
        dialog.save(self, None, lambda d, r: self._on_export_chosen(d, r, name))

    def _on_export_chosen(self, dialog: Gtk.FileDialog, result, name: str) -> None:
        try:
            target = dialog.save_finish(result)
        except GLib.Error:
            return  # cancelled
        try:
            self.store.export_m3u(name, target.get_path())
        except OSError as exc:
            self.status.set_label(f"Could not export {name}: {exc.strerror or exc}")
            return
        self.status.set_label(f"Exported {name}")

    def _on_import_playlist(self, _btn) -> None:
        dialog = Gtk.FileDialog(title="Import playlist")
        dialog.open(self, None, self._on_import_chosen)

    def _on_import_chosen(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            source = dialog.open_finish(result)
        except GLib.Error:
            return  # cancelled
        path = Path(source.get_path())
        name = path.stem.strip()
        try:
            skipped = self.store.import_m3u(path, name)
        except (ValueError, OSError) as exc:
            self.status.set_label(str(exc))
            return
        self.current_playlist = name
        self.refresh_playlists()
        self.populate_track_list()
        note = f" ({skipped} missing file(s) skipped)" if skipped else ""
        self.status.set_label(f"Imported {name}{note}")

    def _on_delete_playlist(self, _btn) -> None:
        if self.current_playlist is None:
            return
        self.store.delete(self.current_playlist)
        self.current_playlist = None
        self.refresh_playlists()
        self.populate_track_list()

    def _selected_track(self) -> Track | None:
        return getattr(self._selected_row(), "track", None)

    def _selected_row(self) -> TrackRow | None:
        return self.track_selection.get_selected_item()

    def _store_rows(self) -> list[TrackRow]:
        """Every row in the list, whether or not search and filter hide it."""
        return [self.track_store.get_item(i) for i in range(self.track_store.get_n_items())]

    def _visible_rows(self) -> list[TrackRow]:
        """The rows the user sees: search and filter applied."""
        return [self._track_filtered.get_item(i) for i in range(self._track_filtered.get_n_items())]

    def _store_index(self, row: TrackRow) -> int:
        """Position of a row in the full list, counting rows that search hides (playlist order)."""
        found, position = self.track_store.find(row)
        return position if found else -1

    def _select_row(self, row: TrackRow) -> None:
        for position, shown in enumerate(self._visible_rows()):
            if shown is row:
                self.track_selection.set_selected(position)
                return

    def _on_list_activated(self, _view, position: int) -> None:
        self._activate_row(self._track_filtered.get_item(position))

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
        row = self._selected_row()
        if row is None:
            return
        if self.browse_by == "queue":
            offset = getattr(row, "queue_offset", None)
            if offset is not None and self.queue.remove_upcoming(offset):
                self.populate_track_list()
            return
        if self.current_playlist is None:
            return
        self.store.remove_track(self.current_playlist, self._store_index(row))
        self.populate_track_list()

    # ---- playback ----------------------------------------------------------

    def _activate_row(self, row: TrackRow | None) -> None:
        if row is None:
            return
        if hasattr(row, "iphone_file"):
            # Play from the read-only mount. Reads only; the mount lasts while the window is open.
            phone_rows = [r for r in self._store_rows() if hasattr(r, "iphone_file")]
            tracks = [dataclasses.replace(read_track(r.iphone_file), stats_key=r.iphone_key)
                      for r in phone_rows]
            start = tracks[phone_rows.index(row)]
            self.queue.set_tracks(tracks, start=start)
            self._play_track(self.queue.current())
            return
        if getattr(row, "queue_offset", None) is not None:
            self._play_track(self.queue.jump(row.queue_offset))  # keep the queue, move within it
            return
        if hasattr(row, "group"):
            self.queue.set_tracks(row.group, start=row.group[0])
            self._play_track(self.queue.current())
            return
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
        self._announce(track)

    def _announce(self, track: Track) -> None:
        """Show a track as the one now playing and count it. Shared by normal and gapless starts."""
        self.now_playing.set_label(track.display_text)
        self._show_art(track.path)
        self.play_btn.set_icon_name(PAUSE_ICON)
        self.stats.record_play(track.play_key)
        self._refresh_row_summary(track.path)
        self._rebuild_if_filtered()
        if self.browse_by == "queue":
            self.populate_track_list()  # the upcoming list changed (also prepares the next file)
        else:
            self._prepare_next()

    def _prepare_next(self) -> None:
        """Hand the player the next track so it can start with no gap. Repeat-one and the end of the list use the normal path."""
        upcoming = self.queue.upcoming()
        nxt = upcoming[0] if upcoming and self.queue.repeat != REPEAT_ONE else None
        self.player.set_next_file(nxt.path if nxt else None)

    def _on_gapless_advance(self) -> None:
        """The player has already started the next track with no gap; catch the queue and the display up."""
        track = self.queue.next()
        if track is not None:
            self._announce(track)

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
            row = self._selected_row()
            if row is not None:
                self._activate_row(row)
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

    @staticmethod
    def _crossfade_index(seconds: float) -> int:
        for i, (secs, _label) in enumerate(CROSSFADE_OPTIONS):
            if secs == seconds:
                return i
        return 0

    def _on_fade_chosen(self, *_args) -> None:
        index = self.fade_dropdown.get_selected()
        if index >= len(CROSSFADE_OPTIONS):
            return
        seconds = CROSSFADE_OPTIONS[index][0]
        self.settings.crossfade = seconds
        self.player.set_crossfade(seconds)

    def _on_eq_chosen(self, *_args) -> None:
        index = self.eq_dropdown.get_selected()
        if index >= len(PRESET_NAMES):
            return
        name = PRESET_NAMES[index]
        self.settings.equalizer = name
        if not self.player.set_equalizer(gains_for(name)):
            self.status.set_label("The equalizer is not available on this system")

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
        self._prepare_next()

    def _on_repeat_clicked(self, _button) -> None:
        self.queue.cycle_repeat()
        self.settings.repeat = self.queue.repeat
        self._update_repeat_button()
        self._prepare_next()

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
        release_phone()
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
    def __init__(self, music_dir: Path | None, store_path: Path, settings_path: Path,
                 stats_path: Path, application_id: str = "local.rhythm.Linux"):
        # application_id is a parameter so a test can run a second instance beside the real one.
        super().__init__(application_id=application_id,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = Settings(settings_path)
        self.settings.load()
        self.music_dir = music_dir or Path(self.settings.music_dir or Path.home() / "Music")
        self.store = PlaylistStore(store_path)
        self.store.load()
        self.stats = TrackStats(stats_path)
        self.stats.load()
        self.connect("activate", self._on_activate)
        self.connect("shutdown", lambda _app: release_phone())

    def _on_activate(self, app: Gtk.Application) -> None:
        MainWindow(app, self.music_dir, self.store, self.settings, self.stats).present()
