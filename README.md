# Rhythm (Linux)

A native Linux music library and player: scan a folder, browse by album or artist, make playlists, rate tracks, and play with gapless playback, crossfade and an equalizer.

Rhythm is an independent project. It is not affiliated with or derived from Apple. See [DESIGN.md](DESIGN.md) for the clean-room rules.

## Requirements

- Python 3.10 or newer
- GTK 4 and PyGObject (system packages)
- GStreamer with the base, good and (for some formats) ugly plugin sets
- mutagen (installed by pip)

On Arch: `sudo pacman -S python-gobject gtk4 gstreamer gst-plugins-base gst-plugins-good gst-plugins-ugly`

Optional, for the iPhone features:
- `libimobiledevice` and `ifuse`: read-only browsing of a connected iPhone
- `kdeconnect` (KDE Connect on the phone too): sending tracks to a paired phone

## Install

The GTK and PyGObject packages come from your system, so create the environment with access to them:

```
python3 -m venv --system-site-packages ~/.venvs/rhythm
~/.venvs/rhythm/bin/pip install .
~/.venvs/rhythm/bin/rhythm-linux
```

To add Rhythm to your application menu, copy the launcher file (it runs the `rhythm-linux` command, so the venv's `bin` folder must be on your `PATH`):

```
install -Dm644 data/rhythm-linux.desktop ~/.local/share/applications/rhythm-linux.desktop
```

Check the installed version with `rhythm-linux --version`.

To run from the source folder without installing:

```
python3 -m rhythm_linux --music-dir ~/Music
```

## Distribution packages

Build files are in the repository:

- Arch: `packaging/arch/PKGBUILD`. Run `makepkg -si` in that folder. It downloads the release tarball from GitHub, so the `v1.0.0` tag must exist (and the checksum must be filled in).
- Debian and Ubuntu: the `debian/` folder at the top of the repository. From an unpacked source tree (`rhythm-linux_1.0.0.orig.tar.gz`), install the build dependencies with `sudo apt build-dep .`, then run `dpkg-buildpackage -us -uc -b`. The build runs the test suite. Supported releases are Debian 13 (trixie) and Ubuntu 24.04 or later. Debian 12 (GTK 4.8) and Ubuntu 22.04 (setuptools 59.6) are too old for this package and apt will refuse to install it there.
- Fedora: `packaging/fedora/rhythm-linux.spec`. Save the GitHub archive for the tag as `~/rpmbuild/SOURCES/rhythm-linux-1.0.0.tar.gz` (the name the spec expects), then run `rpmbuild -ba packaging/fedora/rhythm-linux.spec`.

## Using it

- Choose a music folder with the folder button, or drop a folder onto the window.
- Sidebar: Library, Albums, Artists, Up Next, your playlists, and the iPhone view.
- Keyboard: Space play/pause, Ctrl+F search, Ctrl+Left/Right previous/next, S shuffle, R repeat, M mute.
- "Export shown to folder" copies the tracks in the current list to a folder you pick.
- "Send shown to phone" sends them to a paired phone with KDE Connect.

## Where data is kept

- Playlists: `~/.local/share/rhythm-linux/playlists.json`
- Play counts and ratings: `~/.local/share/rhythm-linux/stats.json`. iPhone tracks are counted under the phone's ID and the file's path on the phone, so the counts do not depend on where the phone is mounted.
- Settings (including the last music folder): `~/.config/rhythm-linux/settings.json`
- Log: `~/.local/share/rhythm-linux/rhythm-linux.log`, with warnings and errors only. It rotates at 1 MB and keeps three old copies (`.1` to `.3`).
- The iPhone view mounts the phone at `~/.cache/rhythm-linux/iphone-mount` and releases it on quit.

If `XDG_DATA_HOME` or `XDG_CONFIG_HOME` is set, the folders above move with it.

Each file is written atomically. If a file is damaged, the app moves it to a `.json.bak` copy and starts with defaults.

To reset the app to its defaults:

1. Quit Rhythm.
2. Delete the files you want to reset: `playlists.json`, `stats.json`, `settings.json`, and any `.json.bak` copies beside them. Deleting the whole `~/.local/share/rhythm-linux/` folder also removes the log.
3. Start Rhythm again. With no saved music folder, it scans `~/Music`; choose another folder with the folder button.

Rhythm does not send any of this data anywhere.

## Limits

- Linux only. The iPhone view is read-only, and the app never writes to the phone's music database. It also does not read that database, so music that exists only there is not shown.
- Tracks are not synced into Apple Music.

## Clean-room statement

Rhythm is written from public documentation (GTK, GStreamer, mutagen, the Python standard library, freedesktop icon names) and its own design. The project rules forbid decompiling, disassembling or inspecting Apple's software, including iTunes for Windows. The repository has no Apple artwork, icons, strings or layout assets; the app uses only generic system icons. Its playlist and stats files are its own JSON formats. The rules are in [DESIGN.md](DESIGN.md).

## Tests

```
pip install -e .[test]
python3 -m pytest
```

The tests cover the logic, not the window; GUI behaviour is checked by hand (see RELEASE_CHECKLIST.md).

## Licence

MIT. See [LICENSE](LICENSE).
