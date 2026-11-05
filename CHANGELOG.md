# Changelog

All notable changes to Rhythm (Linux) are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - not yet released

First release. Rhythm (Linux) is a local music player for GTK 4 with a read-only
view of an iPhone and optional sending to a phone over KDE Connect.

### Library
- Scans a music folder for MP3, AAC/M4A, FLAC, WAV, ALAC and AIFF files, reading tags and cover art (including AIFF ID3 tags).
- Damaged or unsupported files fall back to the filename and do not stop the scan.
- Virtualised track list: 5,000 tracks scan, sort, filter and play without freezing the window.
- Debounced search over title, artist and album.
- Browse views for albums and artists.
- Sort by artist, album, title or file name, and by rating or most played.

### Playback
- Gapless playback from the Up Next queue.
- Crossfade between tracks.
- Equaliser presets.
- Shuffle and repeat (off, all, one).
- Up Next view: reorder and remove queued tracks.

### Ratings, play counts and playlists
- Track ratings and play counts, kept in `stats.json`.
- Filter by rating and play count; filters re-run after a play or rating.
- Playlists: create, rename, delete, add and remove tracks, reorder.
- Import and export playlists as M3U.

### Export and phone
- Export the tracks shown to a folder.
- Read-only iPhone browse and playback, through `ifuse` and `ideviceinfo`. Play counts for iPhone files are keyed by device and file.
- Send the tracks shown to a paired phone with KDE Connect.
- A phone that is locked or unplugged shows an error instead of hanging. A stuck mount is given up after 60 s.
- Missing phone tools (`ifuse`, `ideviceinfo`, `kdeconnect-cli`) are named in the status bar at startup.

### Reliability and data
- Settings, playlists and stats are written so that a crash leaves valid files.
- Damaged `settings.json`, `playlists.json` or `stats.json` is moved to a `.json.bak` copy and the app starts with defaults.
- Warnings and errors go to `rhythm-linux.log` in the data folder (rotated at 1 MB, 3 kept).
- `--version` and `--help` on the command line.

### Accessibility
- Icon-only buttons, sliders, drop-downs, the search entry and album art have accessible names.

### Known limits
- iPhone access is read-only.
- WAV and AIFF files with no ID3 tags show the filename as the title; AIFF text chunks (NAME, AUTH) are not read.
- GStreamer may print one "Trying to dispose element inputselector" warning during long gapless sessions. It comes from playbin internals and does not appear in the app log.
- Tested on one distribution with one iPhone model.
