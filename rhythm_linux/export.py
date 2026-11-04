"""Copy tracks into a folder on this computer. Read-only on the source files."""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExportResult:
    copied: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)


def unique_target(folder: Path, name: str) -> Path:
    """`folder/name`, or `name (2)`, `name (3)`... if that name is taken."""
    candidate = folder / name
    stem, suffix = Path(name).stem, Path(name).suffix
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){suffix}"
        n += 1
    return candidate


def copy_tracks(sources: list[Path], folder: Path) -> ExportResult:
    """Copy each source into `folder`, keeping its file name. Never overwrites."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    result = ExportResult()
    for source in sources:
        source = Path(source)
        try:
            target = unique_target(folder, source.name)
            shutil.copy2(source, target)
            result.copied.append(target)
        except OSError as exc:
            result.failed.append((source, exc.strerror or str(exc)))
    return result
