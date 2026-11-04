import json

import pytest

from rhythm_linux.playlists import PlaylistStore


def test_create_add_remove_persist(tmp_path):
    path = tmp_path / "playlists.json"
    store = PlaylistStore(path)
    store.load()
    store.create("Road")
    store.add_track("Road", "/m/a.mp3")
    store.add_track("Road", "/m/b.mp3")
    store.remove_track("Road", 0)

    reloaded = PlaylistStore(path)
    reloaded.load()
    assert reloaded.names() == ["Road"]
    assert reloaded.tracks("Road") == ["/m/b.mp3"]


def test_rejects_empty_and_duplicate_names(tmp_path):
    store = PlaylistStore(tmp_path / "p.json")
    store.load()
    with pytest.raises(ValueError):
        store.create("   ")
    store.create("Mix")
    with pytest.raises(ValueError):
        store.create("Mix")


def test_corrupt_file_is_backed_up_not_overwritten(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json")
    store = PlaylistStore(path)
    store.load()
    assert store.names() == []
    assert (tmp_path / "p.json.bak").read_text() == "{not json"


def test_file_format_is_plain_json(tmp_path):
    path = tmp_path / "p.json"
    store = PlaylistStore(path)
    store.load()
    store.create("X")
    store.add_track("X", "/m/a.mp3")
    assert json.loads(path.read_text()) == {"X": ["/m/a.mp3"]}


def test_move_track_up_and_down(tmp_path):
    store = PlaylistStore(tmp_path / "p.json")
    store.load()
    store.create("Mix")
    for p in ["/m/a.mp3", "/m/b.mp3", "/m/c.mp3"]:
        store.add_track("Mix", p)
    assert store.move_track("Mix", 2, -1) == 1
    assert store.tracks("Mix") == ["/m/a.mp3", "/m/c.mp3", "/m/b.mp3"]
    assert store.move_track("Mix", 0, -1) == 0  # already at the top: no change
    assert store.move_track("Mix", 2, 1) == 2   # already at the bottom: no change
    assert store.tracks("Mix") == ["/m/a.mp3", "/m/c.mp3", "/m/b.mp3"]
