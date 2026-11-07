"""A file GStreamer cannot play reports the error to the window instead of looking like it plays."""
import shutil

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gst", "1.0")
from gi.repository import GLib  # noqa: E402

from rhythm_linux.player import Player  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("gst-launch-1.0") is None,
                                reason="needs GStreamer")


def _pump(seconds):
    end = GLib.get_monotonic_time() + int(seconds * 1_000_000)
    ctx = GLib.MainContext.default()
    while GLib.get_monotonic_time() < end:
        ctx.iteration(False)


def test_missing_file_reports_an_error_through_the_callback(tmp_path):
    errors = []
    player = Player(on_error=errors.append)
    try:
        player.play_file(str(tmp_path / "not-there.mp3"))
        _pump(2.0)
    finally:
        player.stop()

    assert errors, "the playback error was never reported to the window"
    assert player.error
    assert player.state == Player.STOPPED
    assert not player.has_media
