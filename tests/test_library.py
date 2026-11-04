from rhythm_linux.library import Track, read_track, scan_folder


def test_filename_fallback_when_not_audio(tmp_path):
    f = tmp_path / "Song One.mp3"
    f.write_bytes(b"not really audio")
    t = read_track(f)
    assert t.title == "Song One"
    assert t.artist == "" and t.album == ""


def test_scan_filters_extensions_and_sorts(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "b.flac").write_bytes(b"x")
    (tmp_path / "sub" / "a.mp3").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("skip me")
    tracks = scan_folder(tmp_path)
    assert [Path_name(t) for t in tracks] == ["a", "b"]


def test_search_text_includes_filename():
    t = Track(path="/m/Hello.mp3", title="Hi", artist="Ann", album="Alb")
    assert "hello" in t.search_text and "ann" in t.search_text


def Path_name(track):
    from pathlib import Path
    return Path(track.path).stem
