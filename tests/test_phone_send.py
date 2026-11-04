import subprocess
from types import SimpleNamespace

from rhythm_linux import phone_send


def test_paired_ids_are_parsed_from_id_only_output(monkeypatch):
    monkeypatch.setattr(phone_send, "available", lambda: True)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout="abc_123\n\n def_456 \n", stderr="", returncode=0))

    assert phone_send.paired_device_ids() == ["abc_123", "def_456"]


def test_no_tool_means_no_devices(monkeypatch):
    monkeypatch.setattr(phone_send, "available", lambda: False)
    assert phone_send.paired_device_ids() == []


def test_each_file_is_shared_and_failures_are_kept(monkeypatch, tmp_path):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        name = args[-1]
        if name.endswith("bad.mp3"):
            return SimpleNamespace(returncode=1, stdout="", stderr="device not reachable")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    good, bad = tmp_path / "good.flac", tmp_path / "bad.mp3"

    result = phone_send.send_files("dev1", [good, bad])

    assert result.sent == [good]
    assert result.failed == [(bad, "device not reachable")]
    assert calls[0] == ["kdeconnect-cli", "-d", "dev1", "--share", str(good)]


def test_timeout_is_reported_as_failure(monkeypatch, tmp_path):
    def slow(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 1)

    monkeypatch.setattr(subprocess, "run", slow)
    f = tmp_path / "a.m4a"

    result = phone_send.send_files("dev1", [f])

    assert result.sent == []
    assert result.failed == [(f, "timed out")]
