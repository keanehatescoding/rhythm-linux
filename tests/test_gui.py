"""Window-level checks: the library list, search, rating filter and export of shown tracks.

These run the real window in-process. They need a display (run them under xvfb-run on a
headless machine) and are skipped when GTK cannot start one.
"""
import math
import os
import time
import wave
from pathlib import Path

import pytest

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    pytest.skip("no display: run under xvfb-run to include the window tests", allow_module_level=True)

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

if not Gtk.init_check():
    pytest.skip("GTK could not open the display", allow_module_level=True)

from rhythm_linux.stats import FILTERS  # noqa: E402
from rhythm_linux.ui import RhythmApp  # noqa: E402


def make_wav(path: Path) -> None:
    """A short silent-ish mono WAV; enough for the library to read it."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(
            (int(3000 * math.sin(i / 10))).to_bytes(2, "little", signed=True)
            for i in range(4000)))


TRACKS = ("alpha.wav", "beta.wav", "gamma.wav")


@pytest.fixture(scope="module")
def music(tmp_path_factory):
    folder = tmp_path_factory.mktemp("music")
    for name in TRACKS:
        make_wav(folder / name)
    return folder


@pytest.fixture(scope="module")
def app(music, tmp_path_factory):
    # GTK allows one registered application per process, so the whole module shares one.
    data = tmp_path_factory.mktemp("data")
    application = RhythmApp(music, data / "playlists.json", data / "settings.json",
                            data / "stats.json")
    application.register(None)
    application.activate()
    pump_until(lambda: application.get_active_window() is not None)
    yield application
    application.quit()


@pytest.fixture(autouse=True)
def reset_window(app, music):
    """Each test starts with no search, the 'All tracks' filter and no ratings."""
    win = app.get_active_window()
    for name in TRACKS:
        win.stats.set_rating(str(music / name), 0)
    win.search.set_text("")
    win.filter_dropdown.set_selected(FILTERS.index("All tracks"))
    pump_until(lambda: len(visible_names(win)) == len(TRACKS))
    yield


def pump(seconds: float) -> None:
    ctx = GLib.MainContext.default()
    end = time.time() + seconds
    while time.time() < end:
        ctx.iteration(False)


def pump_until(condition, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end and not condition():
        GLib.MainContext.default().iteration(False)


def visible_names(win) -> list[str]:
    names = []
    index = 0
    row = win.track_list.get_row_at_index(index)
    while row is not None:
        if hasattr(row, "track") and win._filter_row(row):
            names.append(Path(row.track.path).name)
        index += 1
        row = win.track_list.get_row_at_index(index)
    return names


def displayed_names(win) -> list[str]:
    """Rows GTK is actually showing (after the list's own filter has run)."""
    names = []
    row = win.track_list.get_first_child()
    while row is not None:
        if hasattr(row, "track") and row.get_child_visible():
            names.append(Path(row.track.path).name)
        row = row.get_next_sibling()
    return names


def test_library_lists_every_track_in_the_music_folder(app):
    win = app.get_active_window()
    pump_until(lambda: len(visible_names(win)) == 3)

    assert sorted(visible_names(win)) == ["alpha.wav", "beta.wav", "gamma.wav"]


def test_search_leaves_only_matching_tracks(app):
    win = app.get_active_window()
    pump_until(lambda: len(visible_names(win)) == 3)

    win.search.set_text("beta")
    pump_until(lambda: displayed_names(win) == ["beta.wav"])

    assert visible_names(win) == ["beta.wav"]


def test_rating_filter_shows_only_tracks_rated_three_or_more(app, music):
    win = app.get_active_window()
    pump_until(lambda: len(visible_names(win)) == 3)
    win.stats.set_rating(str(music / "alpha.wav"), 4)
    win.stats.set_rating(str(music / "gamma.wav"), 2)

    win.filter_dropdown.set_selected(FILTERS.index("Rated 3+ stars"))
    pump(0.3)

    assert visible_names(win) == ["alpha.wav"]


def test_export_shown_copies_only_the_searched_tracks(app, music, tmp_path):
    win = app.get_active_window()
    pump_until(lambda: len(visible_names(win)) == 3)
    win.search.set_text("gamma")
    pump_until(lambda: displayed_names(win) == ["gamma.wav"])
    dest = tmp_path / "exported"
    dest.mkdir()

    win._export_worker(win._shown_track_paths(), dest)
    pump_until(lambda: (dest / "gamma.wav").exists())
    pump(0.2)

    assert sorted(p.name for p in dest.iterdir()) == ["gamma.wav"]
    assert "Exported 1 of 1" in win.status.get_label()
