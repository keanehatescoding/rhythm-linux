"""The library list is in the order the sort control asks for.

The files carry tags whose Artist and Album orders differ, so a sort that is not applied, or
that reads the wrong choice, shows the same order and fails here. Needs a display (run under
xvfb-run); skipped without one.
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

from mutagen.id3 import TALB, TIT2, TPE1  # noqa: E402
from mutagen.wave import WAVE  # noqa: E402

from rhythm_linux.library import SORT_KEYS  # noqa: E402
from rhythm_linux.stats import STATS_SORTS  # noqa: E402
from rhythm_linux.ui import RhythmApp  # noqa: E402

# (file, title, artist, album). Sorted by artist the order is b (Alpha), a (Bravo), c (Charlie);
# by album it is c (Xray), b (Yankee), a (Zulu).
TRACKS = [
    ("a.wav", "One", "Bravo", "Zulu"),
    ("b.wav", "Two", "Alpha", "Yankee"),
    ("c.wav", "Three", "Charlie", "Xray"),
]
ARTIST_ORDER = ["b.wav", "a.wav", "c.wav"]
ALBUM_ORDER = ["c.wav", "b.wav", "a.wav"]


def make_tagged_wav(path: Path, title: str, artist: str, album: str) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(
            (int(2000 * math.sin(i / 12))).to_bytes(2, "little", signed=True)
            for i in range(8000)))
    audio = WAVE(str(path))
    audio.add_tags()
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.tags.add(TPE1(encoding=3, text=artist))
    audio.tags.add(TALB(encoding=3, text=album))
    audio.save()


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    music = tmp_path_factory.mktemp("sort-music")
    for name, title, artist, album in TRACKS:
        make_tagged_wav(music / name, title, artist, album)
    data = tmp_path_factory.mktemp("sort-data")
    application = RhythmApp(music, data / "playlists.json", data / "settings.json",
                            data / "stats.json", application_id="local.rhythm.SortOrderTest")
    application.register(None)
    application.activate()
    pump_until(lambda: application.get_active_window() is not None)
    yield application
    application.quit()


def pump_until(condition, timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end and not condition():
        GLib.MainContext.default().iteration(False)
    return condition()


def visible_names(win) -> list[str]:
    return [Path(row.track.path).name for row in win._visible_rows() if hasattr(row, "track")]


def choose_sort(win, key: str) -> None:
    names = list(SORT_KEYS) + list(STATS_SORTS)
    win.sort_dropdown.set_active(names.index(key))


def test_sort_by_artist_then_album_orders_the_list(app):
    win = app.get_active_window()
    assert pump_until(lambda: len(visible_names(win)) == len(TRACKS))

    choose_sort(win, "Artist")
    assert pump_until(lambda: visible_names(win) == ARTIST_ORDER)

    choose_sort(win, "Album")
    assert pump_until(lambda: visible_names(win) == ALBUM_ORDER)
