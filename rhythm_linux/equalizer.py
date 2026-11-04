"""Equalizer presets: ten band gains in decibels. No GStreamer here, so it is unit-tested directly."""
from __future__ import annotations

BAND_COUNT = 10
MAX_GAIN_DB = 12.0

PRESETS: dict[str, list[float]] = {
    "Flat": [0.0] * BAND_COUNT,
    "Bass boost": [6.0, 5.0, 4.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "Treble boost": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.5, 4.0, 5.0, 6.0],
    "Vocal": [-2.0, -2.0, 0.0, 3.0, 4.0, 4.0, 3.0, 1.5, 0.0, -1.0],
}
PRESET_NAMES = tuple(PRESETS)
DEFAULT_PRESET = "Flat"


def gains_for(name: str) -> list[float]:
    """Band gains for a preset. Unknown names fall back to Flat."""
    return list(PRESETS.get(name, PRESETS[DEFAULT_PRESET]))


def clamp_gains(gains: list[float]) -> list[float]:
    """Keep every band within the range the equalizer element accepts."""
    return [min(max(float(g), -MAX_GAIN_DB), MAX_GAIN_DB) for g in gains]
