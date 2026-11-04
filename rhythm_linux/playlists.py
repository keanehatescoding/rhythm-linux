"""Playlists stored as JSON: {"Name": ["/abs/path/one.mp3", ...], ...}."""
from __future__ import annotations

import json
import os
from pathlib import Path


class PlaylistStore:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._playlists: dict[str, list[str]] = {}

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top level must be an object")
            self._playlists = {
                str(name): [str(p) for p in paths] for name, paths in data.items()
            }
        except FileNotFoundError:
            self._playlists = {}
        except (ValueError, TypeError):
            # Keep the unreadable file as a backup rather than overwriting it.
            backup = self.path.with_suffix(".json.bak")
            os.replace(self.path, backup)
            self._playlists = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._playlists, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def names(self) -> list[str]:
        return sorted(self._playlists, key=str.lower)

    def tracks(self, name: str) -> list[str]:
        return list(self._playlists[name])

    def create(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("playlist name is empty")
        if name in self._playlists:
            raise ValueError(f"playlist {name!r} already exists")
        self._playlists[name] = []
        self.save()

    def delete(self, name: str) -> None:
        del self._playlists[name]
        self.save()

    def rename(self, old: str, new: str) -> None:
        new = new.strip()
        if not new:
            raise ValueError("playlist name is empty")
        if new == old:
            return
        if new in self._playlists:
            raise ValueError(f"playlist {new!r} already exists")
        # Rebuild the dict so the playlist keeps its place in the file.
        self._playlists = {(new if name == old else name): paths
                           for name, paths in self._playlists.items()}
        self.save()

    def add_track(self, name: str, path: str) -> None:
        self._playlists[name].append(path)
        self.save()

    def remove_track(self, name: str, index: int) -> None:
        del self._playlists[name][index]
        self.save()

    def move_track(self, name: str, index: int, delta: int) -> int:
        """Move one entry up (delta=-1) or down (delta=+1). Returns the entry's new index."""
        items = self._playlists[name]
        target = index + delta
        if not (0 <= index < len(items) and 0 <= target < len(items)):
            return index
        items[index], items[target] = items[target], items[index]
        self.save()
        return target
