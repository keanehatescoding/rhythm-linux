"""Damaged or unreadable audio files do not break a scan: tags fall back to the filename and
the cover is None. Only expected errors are caught, so anything else still shows up in tests."""
import os

import pytest

from rhythm_linux.library import read_cover, read_track

DAMAGED = {
    "empty.mp3": b"",
    "junk.flac": b"not a flac at all" * 20,
    "junk.m4a": b"\x00\x00\x00\x20ftypM4A " + b"\x07" * 100,
    "junk.wav": b"RIFF\xff\xff\xff\xffWAVEfmt " + b"\x00" * 40,
    "junk.aiff": b"FORM\x00\x00\x00\x10AIFFCOMM" + b"\xff" * 30,
}


@pytest.fixture
def damaged(tmp_path):
    for name, data in DAMAGED.items():
        (tmp_path / name).write_bytes(data)
    return tmp_path


@pytest.mark.parametrize("name", sorted(DAMAGED))
def test_damaged_file_falls_back_to_the_filename(damaged, name):
    track = read_track(damaged / name)

    assert track.title == os.path.splitext(name)[0]
    assert (track.artist, track.album) == ("", "")


@pytest.mark.parametrize("name", sorted(DAMAGED))
def test_damaged_file_has_no_cover(damaged, name):
    assert read_cover(damaged / name) is None


def test_missing_file_falls_back_to_the_filename(tmp_path):
    assert read_track(tmp_path / "gone.mp3").title == "gone"
    assert read_cover(tmp_path / "gone.mp3") is None
