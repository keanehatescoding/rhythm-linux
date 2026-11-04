"""Playback order: which track comes next, with shuffle and repeat. No GTK or GStreamer here."""
from __future__ import annotations

import random
from typing import Optional, Sequence

from .library import Track

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = "off", "all", "one"
REPEAT_CYCLE = {REPEAT_OFF: REPEAT_ALL, REPEAT_ALL: REPEAT_ONE, REPEAT_ONE: REPEAT_OFF}


class PlaybackQueue:
    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()
        self._original: list[Track] = []   # tracks in view order
        self._order: list[Track] = []      # play order (shuffled when shuffle is on)
        self._pos = -1
        self.shuffle = False
        self.repeat = REPEAT_OFF

    # ---- building the queue ------------------------------------------------

    def set_tracks(self, tracks: Sequence[Track], start: Optional[Track] = None) -> None:
        """Replace the queue. `start` is the track to play first (defaults to the first)."""
        self._original = list(tracks)
        if self.shuffle:
            rest = list(self._original)
            if start is not None and start in rest:
                rest.remove(start)
            self._rng.shuffle(rest)
            self._order = ([start] if start is not None else []) + rest
            self._pos = 0 if self._order else -1
        else:
            self._order = list(self._original)
            self._pos = self._order.index(start) if start in self._order else (0 if self._order else -1)

    def set_shuffle(self, on: bool) -> None:
        current = self.current()
        self.shuffle = on
        self.set_tracks(self._original, start=current)

    def cycle_repeat(self) -> str:
        self.repeat = REPEAT_CYCLE[self.repeat]
        return self.repeat

    # ---- moving through the queue -------------------------------------------

    def current(self) -> Optional[Track]:
        return self._order[self._pos] if 0 <= self._pos < len(self._order) else None

    def next(self) -> Optional[Track]:
        """Advance and return the next track, or None when playback should stop."""
        if not self._order:
            return None
        if self.repeat == REPEAT_ONE:
            return self.current()
        if self._pos + 1 < len(self._order):
            self._pos += 1
            return self.current()
        if self.repeat == REPEAT_ALL:
            if self.shuffle:
                self.set_tracks(self._original, start=None)  # reshuffle for the next pass
            self._pos = 0
            return self.current()
        return None

    def previous(self) -> Optional[Track]:
        """Step back (wraps with repeat-all); stays on the first track otherwise."""
        if not self._order:
            return None
        if self._pos > 0:
            self._pos -= 1
        elif self.repeat == REPEAT_ALL:
            self._pos = len(self._order) - 1
        return self.current()
