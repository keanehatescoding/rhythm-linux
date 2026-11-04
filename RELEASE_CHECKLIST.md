# Rhythm (Linux): production readiness checklist

Status as of `a69c37c` on `master`. Items marked **open** are not done.

## 1. Packaging and install
- [x] `pyproject.toml` with name, version (0.1.0), Python version and dependencies (mutagen; PyGObject and GStreamer are system packages)
- [x] Install check: installed into a scratch venv with system site packages; `rhythm-linux --help` runs. Still to do on a clean machine.
- [~] Desktop launcher is in `data/rhythm-linux.desktop` and the README says how to install it. Not installed by the package yet, and the icon is still the generic system one.
- [x] Version number: `rhythm-linux --version` (single source in `rhythm_linux/__init__.py`). Not shown in the window yet.

## 2. Documentation
- [x] `README.md`: what the app does, install steps, system packages needed (GTK 4, GStreamer plugins, libimobiledevice, ifuse, KDE Connect)
- [x] Note that iPhone sync is limited to read-only browsing, export and KDE Connect sending
- [x] Arch package names in the README exist (checked with pacman)
- [ ] **open** README install steps run on a clean machine
- [ ] **open** Clean-room statement and licence (MIT or similar, your choice)
- [ ] DESIGN.md is up to date through Milestone 19

## 3. Testing
- [x] Unit tests pass (86 as of this commit)
- [~] Tests run in CI on every push: `.github/workflows/tests.yml` is written and its steps pass in a fresh clone here. Not yet run on GitHub because the repo has no remote.
- [x] GUI tests: `tests/test_gui.py` covers the library list, search, the rating filter and export of shown tracks, using generated WAV files. It runs under `xvfb-run` and is skipped with no display. CI runs it under Xvfb (workflow not yet run on GitHub).
- [ ] **open** Large library: at least 5,000 tracks scanned, sorted, filtered and played without freezing the window
- [ ] **open** Formats: MP3, AAC/M4A, FLAC, WAV, ALAC, AIFF checked for tags, cover art and playback
- [ ] **open** Long session: a few hours of play, shuffle and repeat, with no growth in memory or errors in the log

## 4. Reliability
- [ ] **open** Review the broad `except Exception` catches (in `ui.py` and `iphone.py`) and narrow each to the errors it expects, logging the rest
- [x] Logging: warnings and errors go to `rhythm-linux.log` in the data folder (rotated at 1 MB, 3 kept) and to stderr; the app still starts if the folder cannot be written (`tests/test_logsetup.py`)
- [x] Crash test: the app was killed with SIGKILL during playback (10 runs) and during a scan (10 runs); settings, playlists and stats stayed valid JSON with no `.json.bak` and no leftover temp files. The harness is in the scratchpad, not the repo. Scan kills were not confirmed to land mid-scan.
- [x] Corrupt-data test: damaged `settings.json`, `playlists.json` and `stats.json` are moved to `.json.bak` and the app starts with defaults (`tests/test_corrupt_data.py`)

## 5. Phone features
- [ ] **open** Check at startup that `ifuse`, `ideviceinfo` and `kdeconnect-cli` exist; show a clear message in the UI when one is missing
- [ ] **open** Test on a second distribution and a second iPhone model
- [ ] **open** Play counts for iPhone files: key them by device and file, not by mount path
- [ ] **open** A phone that is unplugged or locked during browse shows an error, not a hang
- [ ] Mount is always released on quit, including quit during a mount (checked)

## 6. Data and privacy
- [ ] **open** Settings and stats location documented, plus how to reset them
- [ ] **open** No network calls except KDE Connect on your own network (confirm by checking the code)
- [ ] Clean-room rule kept: no Apple binaries inspected; no Apple artwork or strings used

## 7. Accessibility and polish
- [ ] **open** Keyboard-only use of every control (tab order, focus visible)
- [ ] **open** Screen reader labels on the icon-only buttons
- [ ] **open** Light and dark system themes both readable
- [ ] **open** The footer progress bar and time readout checked during long tracks (checked once so far)

## 8. Release
- [ ] **open** Changelog with version 1.0.0
- [ ] **open** Tag the release and merge only after the items above that you consider required are done
- [ ] **open** Decide which items are required for 1.0 and which can wait (suggest: sections 1, 2, 3 unit tests and CI, 4, 5 first item)
