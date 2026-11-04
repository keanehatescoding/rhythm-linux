"""Scan a folder for audio files and read their tags."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mutagen import File as MutagenFile

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".aiff", ".wma"}


@dataclass(frozen=True)
class Track:
    path: str
    title: str
    artist: str
    album: str

    @property
    def search_text(self) -> str:
        return f"{self.title} {self.artist} {self.album} {Path(self.path).name}".lower()

    @property
    def display_text(self) -> str:
        if self.artist:
            return f"{self.artist} — {self.title}"
        return self.title


def _tag(tags, key: str) -> str:
    try:
        value = tags.get(key)
    except Exception:
        return ""
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0]
    return str(value).strip()


def read_track(path: str | os.PathLike) -> Track:
    """Read tags for one file. Missing or unreadable tags fall back to the filename."""
    path = os.fspath(path)
    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        audio = None
    tags = getattr(audio, "tags", None) or {}
    title = _tag(tags, "title") or Path(path).stem
    return Track(path=path, title=title, artist=_tag(tags, "artist"), album=_tag(tags, "album"))


def scan_folder(root: str | os.PathLike) -> list[Track]:
    """Return all audio files under root, sorted by artist, album, then title."""
    tracks = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
                tracks.append(read_track(os.path.join(dirpath, name)))
    tracks.sort(key=lambda t: (t.artist.lower(), t.album.lower(), t.title.lower(), t.path))
    return tracks


SORT_KEYS = {
    "Artist": lambda t: (t.artist.lower(), t.album.lower(), t.title.lower(), t.path),
    "Album": lambda t: (t.album.lower(), t.title.lower(), t.path),
    "Title": lambda t: (t.title.lower(), t.artist.lower(), t.path),
    "File name": lambda t: (Path(t.path).name.lower(), t.path),
}


def sort_tracks(tracks: list[Track], by: str) -> list[Track]:
    """Return a new list sorted by one of SORT_KEYS (unknown keys sort by artist)."""
    return sorted(tracks, key=SORT_KEYS.get(by, SORT_KEYS["Artist"]))


def group_tracks(tracks: list[Track], field: str) -> list[tuple[str, list[Track]]]:
    """Group tracks by "album" or "artist". Blank values become "Unknown".

    Groups are sorted by name; tracks inside a group are sorted by file path,
    which usually keeps numbered files in album order.
    """
    groups: dict[str, list[Track]] = {}
    for track in tracks:
        key = (getattr(track, field) or "").strip() or "Unknown"
        groups.setdefault(key, []).append(track)
    return [(name, sorted(group, key=lambda t: t.path))
            for name, group in sorted(groups.items(), key=lambda kv: kv[0].lower())]


def cover_from_audio(audio) -> bytes | None:
    """Pull embedded cover art out of an already-opened mutagen object, if any."""
    if audio is None:
        return None
    # FLAC keeps pictures on the file object itself.
    pictures = getattr(audio, "pictures", None)
    if pictures:
        return pictures[0].data
    tags = getattr(audio, "tags", None)
    if not tags:
        return None
    # MP3 (ID3): APIC frames, e.g. "APIC:Cover".
    if hasattr(tags, "getall"):
        for frame in tags.getall("APIC"):
            return frame.data
        return None
    # MP4/M4A: "covr" atom holds a list of image bytes.
    covers = tags.get("covr") if hasattr(tags, "get") else None
    if covers:
        return bytes(covers[0])
    return None


def read_cover(path: str | os.PathLike) -> bytes | None:
    """Return embedded cover image bytes for a file, or None."""
    try:
        audio = MutagenFile(os.fspath(path))
    except Exception:
        return None
    try:
        return cover_from_audio(audio)
    except Exception:
        return None


def merge_tracks(scanned: list[Track], extra: list[Track]) -> list[Track]:
    """Scanned tracks plus any extra tracks whose paths are not already scanned."""
    seen = {t.path for t in scanned}
    return list(scanned) + [t for t in extra if t.path not in seen]
