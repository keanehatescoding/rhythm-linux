"""Quitting releases the read-only iPhone mount, including when a mount is still in progress.

The mount and unmount calls are replaced with stubs, so this needs no phone and no ifuse.
"""
import subprocess
import threading
import time

import pytest

gi = pytest.importorskip("gi")
gi.require_version("Gtk", "4.0")

from rhythm_linux import iphone, ui  # noqa: E402


@pytest.fixture
def fresh_state(monkeypatch):
    # release_phone sets a one-way flag and reads a module-level thread; give each test its own.
    monkeypatch.setattr(ui, "_phone_released", threading.Event())
    monkeypatch.setattr(ui, "_phone_thread", None)


def test_quit_waits_for_an_in_progress_mount_then_unmounts(fresh_state, monkeypatch):
    order = []

    def slow_mount():
        time.sleep(0.3)
        order.append("mounted")

    monkeypatch.setattr(ui, "_phone_thread", threading.Thread(target=slow_mount))
    ui._phone_thread.start()
    monkeypatch.setattr(iphone, "unmount", lambda _mp: order.append("unmounted"))

    ui.release_phone()

    assert order == ["mounted", "unmounted"]
    assert ui._phone_released.is_set()


def test_quit_with_no_mount_still_unmounts(fresh_state, monkeypatch):
    calls = []
    monkeypatch.setattr(iphone, "unmount", lambda mp: calls.append(mp))

    ui.release_phone()

    assert calls == [iphone.default_mountpoint()]


def test_a_failing_unmount_does_not_stop_quitting(fresh_state, monkeypatch):
    def broken(_mp):
        raise subprocess.SubprocessError("fusermount hung")

    monkeypatch.setattr(iphone, "unmount", broken)

    ui.release_phone()  # must not raise
    assert ui._phone_released.is_set()
