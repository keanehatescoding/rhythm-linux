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

To run from the source folder without installing:

```
python3 -m rhythm_linux --music-dir ~/Music
```

## Using it

- Choose a music folder with the folder button, or drop a folder onto the window.
- Sidebar: Library, Albums, Artists, Up Next, your playlists, and the iPhone view.
- Keyboard: Space play/pause, Ctrl+F search, Ctrl+Left/Right previous/next, S shuffle, R repeat, M mute.
- "Export shown to folder" copies the tracks in the current list to a folder you pick.
- "Send shown to phone" sends them to a paired phone with KDE Connect.

## Where data is kept

- Playlists and play statistics: `~/.local/share/rhythm-linux/` (`playlists.json`, `stats.json`)
- Settings: `~/.config/rhythm-linux/settings.json`
- The iPhone view mounts the phone at `~/.cache/rhythm-linux/iphone-mount` and releases it on quit.

Deleting these files resets the app to its defaults.

## Limits

- Linux only. The iPhone view is read-only, and the app never writes to the phone's music database.
- Tracks are not synced into Apple Music.

## Tests

```
pip install -e .[test]
python3 -m pytest
```

The tests cover the logic, not the window; GUI behaviour is checked by hand (see RELEASE_CHECKLIST.md).

## Licence

To be decided before a public release.
