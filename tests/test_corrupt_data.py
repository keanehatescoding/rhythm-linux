"""Damaged data files are kept as .json.bak and the app starts with empty data."""
from rhythm_linux.playlists import PlaylistStore
from rhythm_linux.settings import Settings
from rhythm_linux.stats import TrackStats


def test_corrupt_playlists_are_backed_up_and_start_empty(tmp_path):
    path = tmp_path / "playlists.json"
    path.write_text("{ not json", encoding="utf-8")

    store = PlaylistStore(path)
    store.load()

    assert store.names() == []
    assert (tmp_path / "playlists.json.bak").read_text(encoding="utf-8") == "{ not json"
    assert not path.exists()


def test_corrupt_stats_are_backed_up_and_start_empty(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")  # valid JSON, wrong shape

    stats = TrackStats(path)
    stats.load()

    assert stats.plays("/any/track.mp3") == 0
    assert stats.rating("/any/track.mp3") == 0
    assert (tmp_path / "stats.json.bak").read_text(encoding="utf-8") == "[1, 2, 3]"


def test_corrupt_settings_are_backed_up_and_use_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("nonsense", encoding="utf-8")

    s = Settings(path)
    s.load()

    assert s.volume == 1.0
    assert s.crossfade == 0.0
    assert (tmp_path / "settings.json.bak").read_text(encoding="utf-8") == "nonsense"


def test_settings_that_is_not_an_object_is_backed_up(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[]", encoding="utf-8")

    s = Settings(path)
    s.load()

    assert s.repeat == "off"
    assert (tmp_path / "settings.json.bak").exists()


def test_saving_after_recovery_writes_a_fresh_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("broken", encoding="utf-8")

    s = Settings(path)
    s.load()
    s.volume = 0.5

    again = Settings(path)
    again.load()
    assert again.volume == 0.5
    assert (tmp_path / "settings.json.bak").read_text(encoding="utf-8") == "broken"
