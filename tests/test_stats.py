import json
from datetime import datetime

from rhythm_linux.stats import TrackStats


def test_rating_defaults_to_zero_and_is_clamped(tmp_path):
    stats = TrackStats(tmp_path / "stats.json")
    stats.load()
    assert stats.rating("/m/a.mp3") == 0
    stats.set_rating("/m/a.mp3", 4)
    assert stats.rating("/m/a.mp3") == 4
    stats.set_rating("/m/a.mp3", 9)
    assert stats.rating("/m/a.mp3") == 5
    stats.set_rating("/m/a.mp3", -2)
    assert stats.rating("/m/a.mp3") == 0


def test_record_play_counts_and_stores_last_played(tmp_path):
    stats = TrackStats(tmp_path / "stats.json")
    stats.load()
    stats.record_play("/m/a.mp3", when=datetime(2026, 11, 4, 15, 2, 0))
    stats.record_play("/m/a.mp3", when=datetime(2026, 11, 5, 9, 0, 0))
    assert stats.plays("/m/a.mp3") == 2
    assert stats.last_played("/m/a.mp3") == "2026-11-05T09:00:00"


def test_values_survive_save_and_reload(tmp_path):
    path = tmp_path / "stats.json"
    first = TrackStats(path)
    first.load()
    first.set_rating("/m/a.mp3", 3)
    first.record_play("/m/a.mp3")

    second = TrackStats(path)
    second.load()
    assert second.rating("/m/a.mp3") == 3
    assert second.plays("/m/a.mp3") == 1


def test_corrupt_file_is_moved_aside(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")  # wrong top-level type
    stats = TrackStats(path)
    stats.load()
    assert stats.plays("/m/a.mp3") == 0
    assert (tmp_path / "stats.json.bak").exists()
    assert not path.exists()


def test_saved_file_is_plain_json(tmp_path):
    path = tmp_path / "stats.json"
    stats = TrackStats(path)
    stats.load()
    stats.set_rating("/m/a.mp3", 5)
    assert json.loads(path.read_text(encoding="utf-8")) == {"/m/a.mp3": {"rating": 5}}
