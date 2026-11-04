import os

from rhythm_linux.iphone import MAX_DEPTH, default_mountpoint, is_mounted, list_audio_files


def test_lists_audio_files_sorted_and_skips_other_files(tmp_path):
    (tmp_path / "Music" / "Artist").mkdir(parents=True)
    (tmp_path / "Music" / "Artist" / "b.m4a").write_bytes(b"x")
    (tmp_path / "Music" / "a.MP3").write_bytes(b"x")
    (tmp_path / "Music" / "cover.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")

    found = list_audio_files(tmp_path)

    assert [p.name for p in found] == ["b.m4a", "a.MP3"]  # sorted by full path


def test_symlinks_are_not_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.mp3").write_bytes(b"x")
    mount = tmp_path / "mount"
    mount.mkdir()
    os.symlink(outside, mount / "link")

    assert list_audio_files(mount) == []


def test_depth_is_capped(tmp_path):
    deep = tmp_path
    for i in range(MAX_DEPTH + 2):
        deep = deep / f"d{i}"
    deep.mkdir(parents=True)
    (deep / "too_deep.mp3").write_bytes(b"x")
    (tmp_path / "shallow.mp3").write_bytes(b"x")

    names = [p.name for p in list_audio_files(tmp_path)]

    assert names == ["shallow.mp3"]


def test_missing_folder_gives_empty_list(tmp_path):
    assert list_audio_files(tmp_path / "nope") == []


def test_unmounted_folder_is_not_reported_mounted(tmp_path):
    assert is_mounted(tmp_path) is False


def test_default_mountpoint_is_in_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_mountpoint() == tmp_path / "rhythm-linux" / "iphone-mount"
