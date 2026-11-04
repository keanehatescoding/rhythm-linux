"""The phone tool check names the features that cannot run and the tools they are missing."""
import shutil

import pytest

from rhythm_linux import phone_tools

PHONE_TOOLS = {"idevice_id", "ideviceinfo", "ifuse", "fusermount", "kdeconnect-cli"}


def fake_which(installed):
    return lambda name: f"/usr/bin/{name}" if name in installed else None


def test_everything_installed_gives_no_notice(monkeypatch):
    monkeypatch.setattr(shutil, "which", fake_which(PHONE_TOOLS))

    assert phone_tools.missing_phone_tools() == {}
    assert phone_tools.startup_notice() == ""


def test_missing_iphone_tool_is_named(monkeypatch):
    monkeypatch.setattr(shutil, "which", fake_which(PHONE_TOOLS - {"ifuse"}))

    assert phone_tools.missing_phone_tools() == {"iPhone browsing": ["ifuse"]}
    assert phone_tools.startup_notice() == "iPhone browsing needs ifuse, which is not installed."


def test_missing_kdeconnect_is_named(monkeypatch):
    monkeypatch.setattr(shutil, "which", fake_which(PHONE_TOOLS - {"kdeconnect-cli"}))

    assert phone_tools.missing_phone_tools() == {"KDE Connect sending": ["kdeconnect-cli"]}


def test_every_missing_feature_is_in_the_notice(monkeypatch):
    monkeypatch.setattr(shutil, "which", fake_which(set()))

    notice = phone_tools.startup_notice()
    assert "iPhone browsing needs" in notice
    assert "KDE Connect sending needs kdeconnect-cli" in notice
