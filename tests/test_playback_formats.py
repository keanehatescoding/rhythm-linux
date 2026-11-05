"""Each supported format plays without error and the position advances.

The sample files are made with ffmpeg and played through the real Player, so these
tests skip when ffmpeg or GStreamer is not available. They need an audio output that
GStreamer can open; on a machine without one they fail, which is the point of the check.
"""
import shutil
import subprocess

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gst", "1.0")
from gi.repository import GLib  # noqa: E402

from rhythm_linux.player import Player  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")

FORMATS = {
    "mp3": ["-c:a", "libmp3lame"],
    "m4a-aac": ["-c:a", "aac"],
    "m4a-alac": ["-c:a", "alac"],
    "flac": ["-c:a", "flac"],
    "wav": ["-c:a", "pcm_s16le"],
    "aiff": ["-c:a", "pcm_s16be", "-write_id3v2", "1"],
}
EXT = {"m4a-aac": "m4a", "m4a-alac": "m4a"}
SECONDS = 3.0
PLAY_FOR = 2.0  # seconds of playback to wait for


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    folder = tmp_path_factory.mktemp("playback")
    paths = {}
    for name, codec in FORMATS.items():
        path = folder / f"{name}.{EXT.get(name, name)}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:duration={SECONDS}", *codec, str(path)], check=True)
        paths[name] = path
    return paths


def _pump(seconds):
    end = GLib.get_monotonic_time() + int(seconds * 1_000_000)
    ctx = GLib.MainContext.default()
    while GLib.get_monotonic_time() < end:
        ctx.iteration(False)


@pytest.mark.parametrize("name", list(FORMATS))
def test_format_plays(samples, name):
    player = Player()
    try:
        player.play_file(str(samples[name]))
        _pump(PLAY_FOR)
        assert player.error is None, player.error
        assert player.state == Player.PLAYING
        assert player.position_seconds() >= 1.0
    finally:
        player.stop()
