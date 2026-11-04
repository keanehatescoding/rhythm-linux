# Rhythm (Linux)

A native Linux music library and player. Not affiliated with or derived from Apple.

## Clean-room rules
- Code is written from public documentation (GTK, GStreamer, mutagen, Python stdlib) and our own design.
- Do not decompile, disassemble, or inspect Apple's binaries (including iTunes for Windows).
- Do not copy Apple artwork, icons, strings, or layout assets. Use generic system icons only.
- The playlist file format is our own JSON format (see `playlists.py`), not a copy of any Apple format.

## Milestone 1 (done)
- Scan a music folder for audio files; read tags with mutagen (fall back to the filename).
- Searchable track list.
- Playlists: create, delete, add tracks, remove tracks; saved as JSON.
- Playback via GStreamer `playbin`: play, pause/resume, stop, previous, next, auto-advance.

## Milestone 2 (done)
- Settings saved to `~/.config/rhythm-linux/settings.json` (last music folder used when `--music-dir` is not given).
- Progress bar with elapsed/total time and click-to-seek.
- Play/pause state tracked by the player, not inferred from GStreamer.

## Milestone 3 (done)
- Sort the library by artist, album, title, or file name (library view only; playlists keep their order).
- Album art: embedded cover (ID3 APIC, MP4 covr, FLAC pictures) shown in the footer while playing.
- Drag and drop: drop a folder to make it the music folder (saved); drop audio files to add them for this session.

## Milestone 4 (done)
- Library scan runs on a background thread; results are ignored if a newer scan has started.
- Track rows are added in batches of 250, so large libraries load without freezing the window.
- Application launcher entry: `~/.local/share/applications/rhythm-linux.desktop`.

## Milestone 5 (done)
- Shuffle (toggle) and repeat (off → all → one) in the footer.
- Playback order lives in `rhythm_linux/queue.py`, separate from the GTK code, so it's unit-tested.
- Turning shuffle on keeps the current track playing first; repeat-all reshuffles on each pass.

## Milestone 6 (done)
- Volume slider (0–100%) and mute toggle in the footer; the level is saved in settings and restored on launch.
- Mute stays on across track changes; moving the slider unmutes.

## Milestone 7 (done)
- Playlists can be reordered with Move up / Move down.
- Dropped files, shuffle, repeat and volume are remembered between launches (`settings.json`).
- Keyboard shortcuts: Space play/pause, Ctrl+F search, Ctrl+Left/Right previous/next, S shuffle, R repeat, M mute. Letter keys are ignored while a text field has focus.

## Milestone 8 (done)
- Albums and Artists views in the sidebar. Each group shows its track count; activating a group plays all of its tracks.
- Grouping lives in `library.group_tracks` (unit-tested). Blank album or artist values are grouped as "Unknown".
- Search filters group names in these views.

## Milestone 9 (done)
- Ratings (0–5 stars) chosen from a dropdown for the selected track. Each track row shows its stars and play count.
- Play count and last-played time are recorded each time a track starts.
- Stored in `stats.json` in the data folder, separate from playlists. Store logic is in `rhythm_linux/stats.py` (unit-tested).
- Sorting by rating and by play count is available in the sort dropdown ("Rating" and "Most played", highest first). Filtering by rating or play count is not yet implemented.

## Milestone 10 (done)
- "Up Next" in the sidebar lists the tracks queued after the current one, in play order.
- Activating a row in Up Next jumps to that track and keeps the rest of the queue.
- With Up Next selected, the Remove and Move up/down buttons remove or reorder queued tracks. Removed tracks stay out of the queue on repeat-all wraps.
- Queue logic is `PlaybackQueue.upcoming()` and `jump()` (unit-tested). Up Next refreshes when the track changes.

## Milestone 11 (done)
- Playlists can be renamed. Select a playlist, type the new name in the "Rename selected playlist" field, and press Enter. Duplicate or empty names are refused with a message.
- Rename keeps the playlist's tracks and its place in the file (`PlaylistStore.rename`, unit-tested).

## Milestone 12 (done)
- Playlists can be exported to M3U (`#EXTM3U` with absolute paths) and imported from M3U. M3U is a plain-text open format.
- Import resolves relative entries against the file's folder, skips files that are missing, and reports how many were skipped. Store logic is `PlaylistStore.export_m3u` and `import_m3u` (unit-tested).

## Milestone 13 (done)
- The playlist and rating buttons above the track list wrap onto more lines in a narrow window, so none run off the edge. Checked with a screenshot in a tiled Hyprland window.

## Later
- iPhone sync (see below). Paused until there is music on the phone or computer to test with.

## iPhone sync status
- Phone is paired and readable via libimobiledevice and `ifuse` (read-only). `usbmuxd` is running.
- The phone currently has no music files, so there is nothing to test a transfer with.
