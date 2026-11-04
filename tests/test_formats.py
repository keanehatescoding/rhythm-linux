"""Tags and cover art are read from each supported format.

The sample files are made with ffmpeg, so these tests skip when ffmpeg is not installed.
"""
import shutil
import subprocess

import pytest

from rhythm_linux.library import read_cover, read_track

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")

TAGS = ["-metadata", "title=Fmt Title", "-metadata", "artist=Tester", "-metadata", "album=Formats"]


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    folder = tmp_path_factory.mktemp("formats")
    cover = folder / "cover.jpg"
    run(["-f", "lavfi", "-i", "color=red:s=64x64", "-frames:v", "1", str(cover)])
    tone = ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-i", str(cover),
            "-map", "0", "-map", "1", "-disposition:v", "attached_pic"]
    art = ["-c:v", "mjpeg"]
    run(tone + ["-c:a", "libmp3lame", *art, *TAGS, str(folder / "mp3.mp3")])
    run(tone + ["-c:a", "aac", *art, *TAGS, str(folder / "aac.m4a")])
    run(tone + ["-c:a", "alac", *art, *TAGS, str(folder / "alac.m4a")])
    run(tone + ["-c:a", "flac", *art, *TAGS, str(folder / "flac.flac")])
    run(["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "pcm_s16le",
         str(folder / "wav.wav")])
    run(["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "pcm_s16be",
         "-write_id3v2", "1", *TAGS, str(folder / "aiff.aiff")])
    return folder


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


@pytest.mark.parametrize("name", ["mp3.mp3", "aac.m4a", "alac.m4a", "flac.flac"])
def test_tags_are_read(samples, name):
    track = read_track(samples / name)

    assert (track.title, track.artist, track.album) == ("Fmt Title", "Tester", "Formats")


@pytest.mark.parametrize("name", ["mp3.mp3", "aac.m4a", "alac.m4a", "flac.flac"])
def test_embedded_cover_is_read(samples, name):
    assert read_cover(samples / name)


def test_aiff_with_id3_tags_is_read(samples):
    track = read_track(samples / "aiff.aiff")

    assert (track.title, track.artist, track.album) == ("Fmt Title", "Tester", "Formats")


def test_untagged_wav_falls_back_to_the_filename(samples):
    track = read_track(samples / "wav.wav")

    assert track.title == "wav"
    assert track.artist == ""
