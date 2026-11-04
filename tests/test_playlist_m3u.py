import pytest

from rhythm_linux.playlists import PlaylistStore


@pytest.fixture
def music(tmp_path):
    folder = tmp_path / "music"
    folder.mkdir()
    for name in ("a.mp3", "b.mp3"):
        (folder / name).write_bytes(b"x")
    return folder


def test_export_then_import_round_trips(tmp_path, music):
    store = PlaylistStore(tmp_path / "p.json")
    store.load()
    store.create("Road")
    store.add_track("Road", str(music / "b.mp3"))
    store.add_track("Road", str(music / "a.mp3"))
    out = tmp_path / "road.m3u"
    store.export_m3u("Road", out)
    assert out.read_text().splitlines()[0] == "#EXTM3U"

    other = PlaylistStore(tmp_path / "q.json")
    other.load()
    assert other.import_m3u(out) == 0
    assert other.names() == ["road"]
    assert other.tracks("road") == [str(music / "b.mp3"), str(music / "a.mp3")]


def test_import_resolves_relative_paths_and_skips_missing(tmp_path, music):
    m3u = music / "list.m3u"
    m3u.write_text("#EXTM3U\n#EXTINF:1,x\na.mp3\n\ngone.mp3\n", encoding="utf-8")
    store = PlaylistStore(tmp_path / "p.json")
    store.load()
    assert store.import_m3u(m3u, name="Mix") == 1
    assert store.tracks("Mix") == [str(music / "a.mp3")]


def test_import_refuses_existing_name(tmp_path, music):
    m3u = music / "list.m3u"
    m3u.write_text("a.mp3\n", encoding="utf-8")
    store = PlaylistStore(tmp_path / "p.json")
    store.load()
    store.create("Mix")
    with pytest.raises(ValueError):
        store.import_m3u(m3u, name="Mix")
