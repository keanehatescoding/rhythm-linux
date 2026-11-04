"""Send files to a paired phone with KDE Connect (kdeconnect-cli). Sends only; never reads phone storage."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SEND_TIMEOUT_SECONDS = 300


@dataclass
class SendResult:
    sent: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)


def available() -> bool:
    return shutil.which("kdeconnect-cli") is not None


def paired_device_ids() -> list[str]:
    """IDs of paired devices. Empty if the tool is missing or nothing is paired."""
    if not available():
        return []
    result = subprocess.run(["kdeconnect-cli", "-l", "--id-only"], capture_output=True,
                            text=True, timeout=30, check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def send_files(device_id: str, paths: list[Path]) -> SendResult:
    """Share each file with the phone. One failure does not stop the others."""
    result = SendResult()
    for path in paths:
        path = Path(path)
        try:
            proc = subprocess.run(["kdeconnect-cli", "-d", device_id, "--share", str(path)],
                                  capture_output=True, text=True,
                                  timeout=SEND_TIMEOUT_SECONDS, check=False)
        except subprocess.TimeoutExpired:
            result.failed.append((path, "timed out"))
            continue
        if proc.returncode == 0:
            result.sent.append(path)
        else:
            reason = (proc.stderr or proc.stdout).strip() or "kdeconnect-cli failed"
            result.failed.append((path, reason))
    return result
