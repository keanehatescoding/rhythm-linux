"""Per-track rating (0-5 stars), play count, and last-played time, stored as JSON.

File format: {"/abs/path/one.mp3": {"rating": 4, "plays": 12, "last_played": "2026-11-04T15:02:00"}, ...}
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

MAX_RATING = 5


class TrackStats:
    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._stats: dict[str, dict] = {}

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top level must be an object")
            self._stats = {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)}
        except FileNotFoundError:
            self._stats = {}
        except (ValueError, TypeError):
            # Keep the unreadable file as a backup rather than overwriting it.
            os.replace(self.path, self.path.with_suffix(".json.bak"))
            self._stats = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._stats, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def rating(self, track_path: str) -> int:
        return int(self._stats.get(track_path, {}).get("rating", 0))

    def plays(self, track_path: str) -> int:
        return int(self._stats.get(track_path, {}).get("plays", 0))

    def last_played(self, track_path: str) -> str:
        return str(self._stats.get(track_path, {}).get("last_played", ""))

    def set_rating(self, track_path: str, stars: int) -> None:
        """Set 0 (no rating) to MAX_RATING stars. Values outside that range are clamped."""
        stars = max(0, min(MAX_RATING, int(stars)))
        entry = self._stats.setdefault(track_path, {})
        entry["rating"] = stars
        self.save()

    def record_play(self, track_path: str, when: datetime | None = None) -> None:
        when = when or datetime.now()
        entry = self._stats.setdefault(track_path, {})
        entry["plays"] = int(entry.get("plays", 0)) + 1
        entry["last_played"] = when.isoformat(timespec="seconds")
        self.save()
