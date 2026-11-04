"""Read-only browsing of a connected iPhone (libimobiledevice + ifuse).

Nothing here writes to the phone. The phone is mounted with `ifuse -o ro`,
so the filesystem refuses writes at the mount level as well.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".flac", ".wav", ".alac", ".aiff", ".aif")
MAX_DEPTH = 6


@dataclass(frozen=True)
class PhoneInfo:
    udid: str
    name: str


def default_mountpoint() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "rhythm-linux" / "iphone-mount"


def tools_missing() -> list[str]:
    """Names of the command-line tools this module needs but cannot find."""
    return [t for t in ("idevice_id", "ideviceinfo", "ifuse", "fusermount") if not shutil.which(t)]


def _run(args: list[str], timeout: float = 15) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"{args[0]} failed")
    return result.stdout


def connected_device() -> PhoneInfo | None:
    """The first iPhone visible over USB, or None."""
    udids = [line.strip() for line in _run(["idevice_id", "-l"]).splitlines() if line.strip()]
    if not udids:
        return None
    udid = udids[0]
    name = _run(["ideviceinfo", "-u", udid, "-k", "DeviceName"]).strip() or "iPhone"
    return PhoneInfo(udid=udid, name=name)


def is_mounted(mountpoint: Path) -> bool:
    target = str(mountpoint.resolve())
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            return any(line.split()[1] == target for line in f if len(line.split()) > 1)
    except OSError:
        return False


def mount_readonly(mountpoint: Path) -> None:
    """Mount the phone's file system read-only at `mountpoint`."""
    mountpoint.mkdir(parents=True, exist_ok=True)
    if is_mounted(mountpoint):
        return
    _run(["ifuse", "-o", "ro", str(mountpoint)], timeout=30)


def unmount(mountpoint: Path) -> None:
    if is_mounted(mountpoint):
        _run(["fusermount", "-u", str(mountpoint)])


def list_audio_files(root: Path) -> list[Path]:
    """Audio files under `root`, sorted by path. Symlinks are not followed."""
    root = Path(root)
    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        folder, depth = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                if depth < MAX_DEPTH:
                    stack.append((Path(entry.path), depth + 1))
            elif entry.name.lower().endswith(AUDIO_EXTENSIONS):
                found.append(Path(entry.path))
    return sorted(found)


def _main(argv: list[str] | None = None) -> int:
    """Print the connected phone and its audio files. Mounts read-only and unmounts after."""
    missing = tools_missing()
    if missing:
        print("Missing tools: " + ", ".join(missing) + " (install libimobiledevice and ifuse)")
        return 1
    try:
        device = connected_device()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Could not talk to the phone: {exc}")
        return 1
    if device is None:
        print("No iPhone found. Plug it in, unlock it and tap Trust.")
        return 1
    print(f"Connected: {device.name} ({device.udid})")
    mountpoint = default_mountpoint()
    try:
        mount_readonly(mountpoint)
        files = list_audio_files(mountpoint)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Mount failed: {exc}")
        return 1
    finally:
        try:
            unmount(mountpoint)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"Warning: could not unmount {mountpoint}: {exc}")
    print(f"Audio files found: {len(files)}")
    for path in files:
        print(path.relative_to(mountpoint))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
