"""Thin wrapper around GStreamer playbin, with gapless and crossfade hand-off between tracks."""
from __future__ import annotations

import time
from typing import Callable, Optional

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

from .equalizer import BAND_COUNT, clamp_gains  # noqa: E402

Gst.init(None)

NS_PER_SECOND = 1_000_000_000
TICK_MS = 100


def crossfade_levels(progress: float, volume: float) -> tuple[float, float]:
    """(outgoing, incoming) volumes part-way through a crossfade. progress runs from 0.0 to 1.0."""
    p = min(max(progress, 0.0), 1.0)
    return (1.0 - p) * volume, p * volume


class _Bin:
    """One playbin with its own equalizer. Two of these take turns across tracks."""

    def __init__(self, name: str):
        self.element = Gst.ElementFactory.make("playbin", name)
        if self.element is None:
            raise RuntimeError("GStreamer 'playbin' element is not available")
        # Optional: without the equalizer element, playback still works, just unfiltered.
        self.eq = Gst.ElementFactory.make("equalizer-10bands", name + "-eq")
        if self.eq is not None:
            self.element.set_property("audio-filter", self.eq)


class Player:
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"

    def __init__(self, on_end_of_stream: Optional[Callable[[], None]] = None,
                 on_gapless: Optional[Callable[[], None]] = None):
        self._on_end = on_end_of_stream
        self._on_gapless = on_gapless  # called on the GTK main loop after a track hand-off
        self._bins = [self._make_bin("rhythm-playbin-a"), self._make_bin("rhythm-playbin-b")]
        self._cur = self._bins[0]              # the bin playing the current track
        self._fade_to: Optional[_Bin] = None   # the incoming bin while a crossfade runs
        self._fade_start = 0.0
        self._fade_seconds = 0.0               # 0 means crossfade is off
        self._next_uri: Optional[str] = None
        self._volume = 1.0
        self._muted = False
        self._eq_gains: Optional[list[float]] = None
        self.state = self.STOPPED  # tracked by us, so it is right immediately after a call
        self.error: Optional[str] = None
        GLib.timeout_add(TICK_MS, self._tick)

    # ---- setup ---------------------------------------------------------------

    def _make_bin(self, name: str) -> _Bin:
        b = _Bin(name)
        bus = b.element.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", lambda _bus, _msg, bin_=b: self._handle_eos(bin_))
        bus.connect("message::error", lambda _bus, msg, bin_=b: self._handle_error(bin_, msg))
        b.element.connect("about-to-finish", lambda _el, bin_=b: self._handle_about_to_finish(bin_))
        return b

    # ---- bus and signal handlers --------------------------------------------

    def _handle_eos(self, b: _Bin) -> None:
        if b is not self._cur:
            return  # a stale bin
        if self._fade_to is not None:
            self._finish_fade()  # the outgoing track ended first; complete the hand-off
            return
        self._set(self.STOPPED)
        if self._on_end is not None:
            self._on_end()

    def _handle_error(self, b: _Bin, message) -> None:
        err, _debug = message.parse_error()
        if b is self._fade_to:
            # The incoming track failed: keep the outgoing track playing and let it end normally.
            self._cancel_fade()
            self._next_uri = None
            return
        if b is not self._cur:
            return
        self.error = err.message
        self._set(self.STOPPED)

    def _handle_about_to_finish(self, b: _Bin) -> None:
        # Runs on a GStreamer streaming thread, so it only sets the URI and
        # hands the UI update to the GTK main loop.
        if b is not self._cur or self._next_uri is None or self._fade_to is not None:
            return
        # playbin says "about to finish" roughly one second early, which is inside the
        # crossfade window. When a fade will run for this track, leave the hand-off to _tick.
        if self._fade_seconds > 0 and self.duration_seconds() > 2 * self._fade_seconds:
            return
        b.element.set_property("uri", self._next_uri)
        self._next_uri = None
        if self._on_gapless is not None:
            GLib.idle_add(self._notify_gapless)

    def _notify_gapless(self) -> bool:
        self._on_gapless()
        return False

    # ---- crossfade -----------------------------------------------------------

    def _tick(self) -> bool:
        """Runs every TICK_MS on the main loop: drives an active crossfade or starts one."""
        if self._fade_to is not None:
            self._update_fade()
            return True
        if self.state != self.PLAYING or self._next_uri is None or self._fade_seconds <= 0:
            return True
        duration = self.duration_seconds()
        if duration <= 2 * self._fade_seconds:
            return True  # too short for a fade; the gapless hand-off handles it
        if duration - self.position_seconds() <= self._fade_seconds:
            self._start_fade()
        return True

    def _start_fade(self) -> None:
        incoming = self._bins[1] if self._cur is self._bins[0] else self._bins[0]
        incoming.element.set_state(Gst.State.NULL)
        incoming.element.set_property("uri", self._next_uri)
        incoming.element.set_property("volume", 0.0)
        incoming.element.set_property("mute", self._muted)
        self._next_uri = None
        self._fade_to = incoming
        self._fade_start = time.monotonic()
        incoming.element.set_state(Gst.State.PLAYING)

    def _update_fade(self) -> None:
        progress = (time.monotonic() - self._fade_start) / self._fade_seconds
        out_vol, in_vol = crossfade_levels(progress, self._volume)
        self._cur.element.set_property("volume", out_vol)
        self._fade_to.element.set_property("volume", in_vol)
        if progress >= 1.0:
            self._finish_fade()

    def _finish_fade(self) -> None:
        old = self._cur
        self._cur = self._fade_to
        self._fade_to = None
        old.element.set_state(Gst.State.NULL)
        self._cur.element.set_property("volume", self._volume)
        if self._on_gapless is not None:
            GLib.idle_add(self._notify_gapless)

    def _cancel_fade(self) -> None:
        if self._fade_to is None:
            return
        self._fade_to.element.set_state(Gst.State.NULL)
        self._fade_to = None
        self._cur.element.set_property("volume", self._volume)

    def set_crossfade(self, seconds: float) -> None:
        """Overlap the end of each track with the start of the next. 0 turns it off."""
        self._fade_seconds = max(0.0, float(seconds))

    # ---- next track ----------------------------------------------------------

    def set_next_file(self, path: Optional[str]) -> None:
        """File to start with no gap when the current one ends. None means stop at the end as usual."""
        self._next_uri = Gst.filename_to_uri(path) if path else None

    # ---- transport -----------------------------------------------------------

    def _set(self, state: str) -> None:
        self.state = state
        gst_state = {self.STOPPED: Gst.State.NULL,
                     self.PAUSED: Gst.State.PAUSED,
                     self.PLAYING: Gst.State.PLAYING}[state]
        if state == self.STOPPED:
            self._cancel_fade()
        self._cur.element.set_state(gst_state)
        if self._fade_to is not None:
            self._fade_to.element.set_state(gst_state)

    def play_file(self, path: str) -> None:
        self.error = None
        self._next_uri = None
        self._set(self.STOPPED)
        self._cur.element.set_property("uri", Gst.filename_to_uri(path))
        self._cur.element.set_property("volume", self._volume)
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
        ok, pos = self._cur.element.query_position(Gst.Format.TIME)
        return pos / NS_PER_SECOND if ok and pos >= 0 else 0.0

    def duration_seconds(self) -> float:
        ok, dur = self._cur.element.query_duration(Gst.Format.TIME)
        return dur / NS_PER_SECOND if ok and dur >= 0 else 0.0

    def seek_seconds(self, seconds: float) -> None:
        if self.state == self.STOPPED:
            return
        flags = Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT
        self._cur.element.seek_simple(Gst.Format.TIME, flags, int(max(seconds, 0) * NS_PER_SECOND))

    # ---- sound -------------------------------------------------------------

    def set_volume(self, value: float) -> None:
        """Volume from 0.0 (silent) to 1.0 (normal level). A running crossfade picks it up on its next step."""
        self._volume = min(max(float(value), 0.0), 1.0)
        if self._fade_to is None:
            self._cur.element.set_property("volume", self._volume)

    def volume(self) -> float:
        return self._volume

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        for b in self._bins:
            b.element.set_property("mute", self._muted)

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def equalizer_available(self) -> bool:
        return self._bins[0].eq is not None

    def set_equalizer(self, gains: list[float]) -> bool:
        """Set the ten band gains in dB. Returns False if the equalizer element is missing."""
        if not self.equalizer_available:
            return False
        self._eq_gains = clamp_gains(gains)[:BAND_COUNT]
        for b in self._bins:
            for i, gain in enumerate(self._eq_gains):
                b.eq.set_property(f"band{i}", gain)
        return True
