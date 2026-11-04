"""User settings stored as JSON in the XDG config directory."""
from __future__ import annotations

import json
import os
from pathlib import Path


class Settings:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._data: dict = {}

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = data if isinstance(data, dict) else {}
        except (FileNotFoundError, ValueError):
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    @property
    def music_dir(self) -> str | None:
        value = self._data.get("music_dir")
        return value if isinstance(value, str) and value else None

    @music_dir.setter
    def music_dir(self, value: str) -> None:
        self._data["music_dir"] = value
        self.save()

    @property
    def volume(self) -> float:
        value = self._data.get("volume", 1.0)
        return min(max(float(value), 0.0), 1.0) if isinstance(value, (int, float)) else 1.0

    @volume.setter
    def volume(self, value: float) -> None:
        self._data["volume"] = round(min(max(float(value), 0.0), 1.0), 2)
        self.save()

    @property
    def shuffle(self) -> bool:
        return bool(self._data.get("shuffle", False))

    @shuffle.setter
    def shuffle(self, value: bool) -> None:
        self._data["shuffle"] = bool(value)
        self.save()

    @property
    def repeat(self) -> str:
        value = self._data.get("repeat", "off")
        return value if value in ("off", "all", "one") else "off"

    @repeat.setter
    def repeat(self, value: str) -> None:
        self._data["repeat"] = value
        self.save()

    @property
    def extra_files(self) -> list[str]:
        value = self._data.get("extra_files", [])
        return [str(p) for p in value] if isinstance(value, list) else []

    @extra_files.setter
    def extra_files(self, paths: list[str]) -> None:
        self._data["extra_files"] = [str(p) for p in paths]
        self.save()
