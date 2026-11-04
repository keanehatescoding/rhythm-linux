"""Thin wrapper around GStreamer playbin."""
from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from .equalizer import BAND_COUNT, clamp_gains  # noqa: E402

Gst.init(None)

NS_PER_SECOND = 1_000_000_000


class Player:
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"

    def __init__(self, on_end_of_stream: Optional[Callable[[], None]] = None,
                 on_gapless: Optional[Callable[[], None]] = None):
        self._playbin = Gst.ElementFactory.make("playbin", "rhythm-playbin")
        if self._playbin is None:
            raise RuntimeError("GStreamer 'playbin' element is not available")
        self._on_end = on_end_of_stream
        self._on_gapless = on_gapless  # called on the GTK main loop after a gapless switch
        self._next_uri: Optional[str] = None
        self.state = self.STOPPED  # tracked by us, so it is right immediately after a call
        self.error: Optional[str] = None
        self._playbin.connect("about-to-finish", self._handle_about_to_finish)
        # Optional: without the equalizer element, playback still works, just unfiltered.
        self._eq = Gst.ElementFactory.make("equalizer-10bands", "rhythm-eq")
        if self._eq is not None:
            self._playbin.set_property("audio-filter", self._eq)
        bus = self._playbin.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._handle_eos)
        bus.connect("message::error", self._handle_error)

    def _handle_eos(self, _bus, _message) -> None:
        self._set(self.STOPPED)
        if self._on_end is not None:
            self._on_end()

    def set_next_file(self, path: Optional[str]) -> None:
        """File to start with no gap when the current one ends. None means stop at the end as usual."""
        self._next_uri = Gst.filename_to_uri(path) if path else None

    def _handle_about_to_finish(self, _playbin) -> None:
        # Runs on a GStreamer streaming thread, so it only sets the URI and
        # hands the UI update to the GTK main loop.
        if self._next_uri is None:
            return
        self._playbin.set_property("uri", self._next_uri)
        self._next_uri = None
        if self._on_gapless is not None:
            GLib.idle_add(self._notify_gapless)

    def _notify_gapless(self) -> bool:
        self._on_gapless()
        return False

    def _handle_error(self, _bus, message) -> None:
        err, _debug = message.parse_error()
        self.error = err.message
        self._set(self.STOPPED)

    def _set(self, state: str) -> None:
        self.state = state
        gst_state = {self.STOPPED: Gst.State.NULL,
                     self.PAUSED: Gst.State.PAUSED,
                     self.PLAYING: Gst.State.PLAYING}[state]
        self._playbin.set_state(gst_state)

    def play_file(self, path: str) -> None:
        self.error = None
        self._next_uri = None
        self._set(self.STOPPED)
        self._playbin.set_property("uri", Gst.filename_to_uri(path))
        self._set(self.PLAYING)

    def pause(self) -> None:
        if self.state == self.PLAYING:
            self._set(self.PAUSED)

    def resume(self) -> None:
        if self.state == self.PAUSED:
            self._set(self.PLAYING)

    def stop(self) -> None:
        self._set(self.STOPPED)

    @property
    def is_playing(self) -> bool:
        return self.state == self.PLAYING

    @property
    def has_media(self) -> bool:
        return self.state != self.STOPPED

    def position_seconds(self) -> float:
        ok, pos = self._playbin.query_position(Gst.Format.TIME)
        return pos / NS_PER_SECOND if ok and pos >= 0 else 0.0

    def duration_seconds(self) -> float:
        ok, dur = self._playbin.query_duration(Gst.Format.TIME)
        return dur / NS_PER_SECOND if ok and dur >= 0 else 0.0

    @property
    def equalizer_available(self) -> bool:
        return self._eq is not None

    def set_equalizer(self, gains: list[float]) -> bool:
        """Set the ten band gains in dB. Returns False if the equalizer element is missing."""
        if self._eq is None:
            return False
        for i, gain in enumerate(clamp_gains(gains)[:BAND_COUNT]):
            self._eq.set_property(f"band{i}", gain)
        return True

    def set_volume(self, value: float) -> None:
        """Volume from 0.0 (silent) to 1.0 (normal level)."""
        self._playbin.set_property("volume", min(max(float(value), 0.0), 1.0))

    def volume(self) -> float:
        return float(self._playbin.get_property("volume"))

    def set_muted(self, muted: bool) -> None:
        self._playbin.set_property("mute", bool(muted))

    @property
    def muted(self) -> bool:
        return bool(self._playbin.get_property("mute"))

    def seek_seconds(self, seconds: float) -> None:
        if self.state == self.STOPPED:
            return
        flags = Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT
        self._playbin.seek_simple(Gst.Format.TIME, flags, int(max(seconds, 0) * NS_PER_SECOND))
