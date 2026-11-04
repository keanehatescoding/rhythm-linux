"""Play counts for iPhone files are keyed by device and file, not by the mount path."""
from pathlib import Path

from rhythm_linux import iphone
from rhythm_linux.library import Track
from rhythm_linux.stats import TrackStats


def test_key_does_not_depend_on_the_mount_path():
    file_on_phone = Path("/mnt/one/Music/song.mp3")

    key_here = iphone.play_key("UDID-A", Path("/mnt/one"), file_on_phone)
    key_elsewhere = iphone.play_key("UDID-A", Path("/mnt/two"), Path("/mnt/two/Music/song.mp3"))

    assert key_here == key_elsewhere == "iphone:UDID-A:Music/song.mp3"


def test_two_phones_with_the_same_file_get_different_keys():
    mount = Path("/mnt/phone")
    file = mount / "Music" / "song.mp3"

    assert iphone.play_key("UDID-A", mount, file) != iphone.play_key("UDID-B", mount, file)


def test_play_counts_stay_separate_per_phone(tmp_path):
    stats = TrackStats(tmp_path / "stats.json")
    mount = Path("/mnt/phone")
    file = mount / "Music" / "song.mp3"

    stats.record_play(iphone.play_key("UDID-A", mount, file))
    stats.record_play(iphone.play_key("UDID-A", mount, file))
    stats.record_play(iphone.play_key("UDID-B", mount, file))

    assert stats.plays(iphone.play_key("UDID-A", mount, file)) == 2
    assert stats.plays(iphone.play_key("UDID-B", mount, file)) == 1


def test_a_track_counts_under_its_stats_key_when_it_has_one():
    plain = Track(path="/home/me/Music/a.mp3", title="a", artist="", album="")
    phone = Track(path="/mnt/phone/Music/a.mp3", title="a", artist="", album="",
                  stats_key="iphone:UDID-A:Music/a.mp3")

    assert plain.play_key == "/home/me/Music/a.mp3"
    assert phone.play_key == "iphone:UDID-A:Music/a.mp3"
