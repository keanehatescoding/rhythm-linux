"""The footer time readout: m:ss under an hour, h:mm:ss from an hour on."""
import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")

from rhythm_linux.ui import _format_time  # noqa: E402


@pytest.mark.parametrize("seconds, text", [
    (0, "0:00"),
    (5.9, "0:05"),
    (59.99, "0:59"),
    (60, "1:00"),
    (3599, "59:59"),
    (3600, "1:00:00"),
    (4500, "1:15:00"),
    (36000 + 61, "10:01:01"),
])
def test_format_time(seconds, text):
    assert _format_time(seconds) == text
