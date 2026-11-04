import json

from rhythm_linux.settings import Settings


def test_music_dir_round_trip(tmp_path):
    path = tmp_path / "cfg" / "settings.json"
    s = Settings(path)
    s.load()
    assert s.music_dir is None
    s.music_dir = "/music/here"

    again = Settings(path)
    again.load()
    assert again.music_dir == "/music/here"
    assert json.loads(path.read_text()) == {"music_dir": "/music/here"}


def test_bad_json_is_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2]")
    s = Settings(path)
    s.load()
    assert s.music_dir is None


def test_volume_defaults_to_full_and_clamps(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.load()
    assert s.volume == 1.0
    s.volume = 1.7
    assert s.volume == 1.0  # clamped
    s.volume = 0.25
    again = Settings(path)
    again.load()
    assert again.volume == 0.25


def test_shuffle_repeat_and_extra_files_persist(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.load()
    assert (s.shuffle, s.repeat, s.extra_files) == (False, "off", [])
    s.shuffle = True
    s.repeat = "all"
    s.extra_files = ["/x/a.mp3", "/x/b.flac"]
    again = Settings(path)
    again.load()
    assert again.shuffle is True
    assert again.repeat == "all"
    assert again.extra_files == ["/x/a.mp3", "/x/b.flac"]


def test_bad_repeat_value_falls_back_to_off(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"repeat": "sometimes"}')
    s = Settings(path)
    s.load()
    assert s.repeat == "off"


def test_equalizer_preset_round_trips(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.load()
    assert s.equalizer == "Flat"
    s.equalizer = "Vocal"
    again = Settings(path)
    again.load()
    assert again.equalizer == "Vocal"
