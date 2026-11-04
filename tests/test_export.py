from rhythm_linux.export import copy_tracks, unique_target


def test_copies_files_keeping_names_and_content(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "song.mp3").write_bytes(b"audio")
    dest = tmp_path / "out"

    result = copy_tracks([src / "song.mp3"], dest)

    assert result.copied == [dest / "song.mp3"]
    assert result.failed == []
    assert (dest / "song.mp3").read_bytes() == b"audio"


def test_never_overwrites_an_existing_file(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "song.mp3").write_bytes(b"new")
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "song.mp3").write_bytes(b"old")

    result = copy_tracks([src / "song.mp3"], dest)

    assert result.copied == [dest / "song (2).mp3"]
    assert (dest / "song.mp3").read_bytes() == b"old"
    assert (dest / "song (2).mp3").read_bytes() == b"new"


def test_missing_source_is_reported_and_others_still_copy(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "good.flac").write_bytes(b"x")
    dest = tmp_path / "out"

    result = copy_tracks([src / "gone.mp3", src / "good.flac"], dest)

    assert result.copied == [dest / "good.flac"]
    assert len(result.failed) == 1
    assert result.failed[0][0] == src / "gone.mp3"


def test_unique_target_counts_up(tmp_path):
    (tmp_path / "a.m4a").write_bytes(b"x")
    (tmp_path / "a (2).m4a").write_bytes(b"x")
    assert unique_target(tmp_path, "a.m4a") == tmp_path / "a (3).m4a"
