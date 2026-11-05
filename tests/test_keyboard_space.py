"""Space on a focused button activates that button; Space elsewhere play/pauses.

Before this check, the window's Space shortcut ran first and took Space from the footer
Stop and Mute buttons. These tests call the window's key handler directly, so they need a
display (run under xvfb-run on a headless machine) and are skipped without one.
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
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

if not Gtk.init_check():
    pytest.skip("GTK could not open the display", allow_module_level=True)

from rhythm_linux.ui import RhythmApp  # noqa: E402


def pump_until(condition, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end and not condition():
        GLib.MainContext.default().iteration(False)
        time.sleep(0.01)
    return condition()


def make_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(
            (int(2000 * math.sin(i / 12))).to_bytes(2, "little", signed=True)
            for i in range(8000 * 20)))


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    folder = tmp_path_factory.mktemp("music")
    make_wav(folder / "long.wav")
    data = tmp_path_factory.mktemp("data")
    # A separate application ID lets this module run beside the other window tests.
    application = RhythmApp(folder, data / "playlists.json", data / "settings.json",
                            data / "stats.json", application_id="local.rhythm.KeyboardSpaceTest")
    application.register(None)
    application.activate()
    pump_until(lambda: application.get_active_window() is not None)
    yield application
    application.quit()


def find_button(widget, label):
    # Footer buttons are icons with a tooltip, so match either the label or the tooltip.
    if isinstance(widget, Gtk.Button) and label in (widget.get_label(), widget.get_tooltip_text()):
        return widget
    child = widget.get_first_child()
    while child is not None:
        found = find_button(child, label)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def test_space_on_focused_stop_stops_instead_of_toggling(app):
    win = app.get_active_window()
    win.player.play_file(str(app.music_dir / "long.wav"))
    pump_until(lambda: win.player.is_playing)
    stop = find_button(win, "Stop")
    assert stop is not None
    stop.grab_focus()
    assert pump_until(lambda: win.get_focus() is stop)

    handled = win._on_key(None, Gdk.KEY_space, 0, 0)

    # The window leaves Space to the focused button, so GTK presses Stop, not play/pause.
    assert handled is False
    assert win.player.is_playing  # the window's own shortcut did not pause the track


def test_space_with_no_control_focused_still_toggles_play(app):
    win = app.get_active_window()
    win.player.play_file(str(app.music_dir / "long.wav"))
    pump_until(lambda: win.player.is_playing)
    win.set_focus(None)
    assert win.get_focus() is None

    handled = win._on_key(None, Gdk.KEY_space, 0, 0)

    assert handled is True
    assert not win.player.is_playing
