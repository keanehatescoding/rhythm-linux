from types import SimpleNamespace

from rhythm_linux.library import (Track, cover_from_audio, group_tracks, read_cover,
                                  sort_tracks)


def _t(path, title, artist, album):
    return Track(path=path, title=title, artist=artist, album=album)


def test_group_by_album_sorts_groups_and_tracks():
    tracks = [
        _t("/m/b.mp3", "Second", "Ann", "Zebra"),
        _t("/m/a.mp3", "First", "Ann", "Zebra"),
        _t("/m/c.mp3", "Solo", "Bo", "apple"),
    ]
    groups = group_tracks(tracks, "album")
    assert [name for name, _ in groups] == ["apple", "Zebra"]
    assert [t.path for t in groups[1][1]] == ["/m/a.mp3", "/m/b.mp3"]


def test_group_by_artist_uses_unknown_for_blank_values():
    tracks = [_t("/m/1.mp3", "A", "", ""), _t("/m/2.mp3", "B", "Ann", "")]
    groups = dict(group_tracks(tracks, "artist"))
    assert set(groups) == {"Unknown", "Ann"}
    assert len(groups["Unknown"]) == 1


def test_sort_by_artist_then_album_then_title():
    tracks = [
        _t("/m/3.mp3", "B song", "Zed", "A"),
        _t("/m/1.mp3", "A song", "Ann", "Z"),
        _t("/m/2.mp3", "C song", "Ann", "Y"),
    ]
    assert [t.title for t in sort_tracks(tracks, "Artist")] == ["C song", "A song", "B song"]


def test_sort_by_title_and_file_name():
    tracks = [_t("/m/b.mp3", "Alpha", "", ""), _t("/m/a.mp3", "Zulu", "", "")]
    assert [t.title for t in sort_tracks(tracks, "Title")] == ["Alpha", "Zulu"]
    assert [t.path for t in sort_tracks(tracks, "File name")] == ["/m/a.mp3", "/m/b.mp3"]


def test_unknown_sort_key_falls_back_to_artist():
    tracks = [_t("/m/1.mp3", "x", "B", ""), _t("/m/2.mp3", "y", "A", "")]
    assert sort_tracks(tracks, "nonsense")[0].artist == "A"


def test_cover_from_mp4_style_tags():
    audio = SimpleNamespace(pictures=None, tags={"covr": [b"\x89PNGdata"]})
    assert cover_from_audio(audio) == b"\x89PNGdata"


def test_cover_from_flac_style_pictures():
    audio = SimpleNamespace(pictures=[SimpleNamespace(data=b"JPEG")], tags=None)
    assert cover_from_audio(audio) == b"JPEG"


def test_no_cover_returns_none(tmp_path):
    assert cover_from_audio(SimpleNamespace(pictures=None, tags={})) is None
    f = tmp_path / "x.mp3"
    f.write_bytes(b"not audio")
    assert read_cover(f) is None


def test_merge_keeps_scanned_then_extra_without_duplicates():
    from rhythm_linux.library import merge_tracks
    a = _t("/m/a.mp3", "A", "", "")
    b = _t("/m/b.mp3", "B", "", "")
    a_dropped = _t("/m/a.mp3", "A (dropped)", "", "")
    merged = merge_tracks([a], [a_dropped, b])
    assert [t.path for t in merged] == ["/m/a.mp3", "/m/b.mp3"]
    assert merged[0].title == "A"
