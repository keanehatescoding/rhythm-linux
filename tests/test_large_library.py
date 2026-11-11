"""A 5,000-track library: every track is shown after the scan, and search narrows the list
without a long stall on the UI thread.

The window runs in a child process with its own application id, so it does not clash with the
window the other tests register. Needs a display (run under xvfb-run); skipped without one.
"""
import json
import os
import subprocess
import sys

import pytest

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    pytest.skip("no display: run under xvfb-run to include the window tests", allow_module_level=True)

COUNT = 5000

# Runs in the child process. Prints one JSON line with the measurements.
CHILD = r'''
import json, math, sys, tempfile, time, wave
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk
if not Gtk.init_check():
    raise SystemExit("GTK could not open the display")

from rhythm_linux.library import SORT_KEYS, read_track
from rhythm_linux.stats import STATS_SORTS
from rhythm_linux.ui import RhythmApp

COUNT = int(sys.argv[1])
root = Path(tempfile.mkdtemp(prefix="large-lib-"))
for a in range(50):
    (root / f"Artist {a:02d}" / "Album").mkdir(parents=True)
for i in range(COUNT):
    with wave.open(str(root / f"Artist {i % 50:02d}" / "Album" / f"track{i:05d}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)

data = root / "_data"
data.mkdir()
app = RhythmApp(root, data / "p.json", data / "s.json", data / "st.json",
                application_id="local.rhythm.LargeLibraryTest")
app.register(None)
ctx = GLib.MainContext.default()
app.activate()
win = None
while win is None:
    ctx.iteration(False)
    win = app.get_active_window()

longest = 0.0

def pump_until(condition, timeout):
    global longest
    end = time.time() + timeout
    while time.time() < end:
        t0 = time.time()
        ctx.iteration(False)
        longest = max(longest, time.time() - t0)
        if condition():
            return True
    return False

def shown():
    return sum(1 for row in win._visible_rows() if hasattr(row, "track"))

result = {}
result["scan_ok"] = pump_until(lambda: shown() == COUNT, 240)
result["scan_longest_pause"] = longest

longest = 0.0
win.search.set_text("track04999")
result["search_ok"] = pump_until(lambda: shown() == 1, 60)
result["search_longest_pause"] = longest
result["search_shown"] = shown()

win.search.set_text("")
result["clear_ok"] = pump_until(lambda: shown() == COUNT, 60)
result["clear_shown"] = shown()

longest = 0.0
names = list(SORT_KEYS) + list(STATS_SORTS)
win.sort_dropdown.set_active(names.index("Album"))
pump_until(lambda: False, 1.0)  # let the sort run and any work it starts finish
result["sort_shown"] = shown()
result["sort_longest_pause"] = longest

longest = 0.0
track = read_track(root / "Artist 00" / "Album" / "track00000.wav")
win._play_track(track)
result["play_ok"] = pump_until(lambda: win.player.has_media, 10)
result["play_longest_pause"] = longest

print("RESULT " + json.dumps(result), flush=True)
app.quit()
'''


def test_five_thousand_tracks_scan_and_search():
    completed = subprocess.run([sys.executable, "-c", CHILD, str(COUNT)],
                               capture_output=True, text=True, timeout=600)
    line = next((l for l in completed.stdout.splitlines() if l.startswith("RESULT ")), None)
    assert line is not None, f"child failed:\n{completed.stdout}\n{completed.stderr}"
    result = json.loads(line[len("RESULT "):])

    assert result["scan_ok"], "not every track was shown after the scan"
    assert result["search_ok"] and result["search_shown"] == 1
    assert result["clear_ok"] and result["clear_shown"] == COUNT
    assert result["sort_shown"] == COUNT
    assert result["play_ok"], "playback did not start"
    assert result["sort_longest_pause"] < 1.0
    assert result["play_longest_pause"] < 1.0
    # Generous limit: the measured longest pause is about 80 ms, so this only catches a real freeze.
    assert result["search_longest_pause"] < 1.0
    assert result["scan_longest_pause"] < 1.0
