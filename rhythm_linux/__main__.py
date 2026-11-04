import argparse
import sys
from pathlib import Path

from gi.repository import GLib

from . import __version__
from .ui import RhythmApp


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rhythm-linux")
    parser.add_argument("--version", action="version", version=f"rhythm-linux {__version__}")
    parser.add_argument("--music-dir", type=Path, default=None,
                        help="folder to scan (default: last folder you chose, else ~/Music)")
    args = parser.parse_args(argv)

    data_dir = Path(GLib.get_user_data_dir()) / "rhythm-linux"
    config_dir = Path(GLib.get_user_config_dir()) / "rhythm-linux"
    music_dir = args.music_dir.expanduser() if args.music_dir else None
    app = RhythmApp(music_dir=music_dir,
                    store_path=data_dir / "playlists.json",
                    settings_path=config_dir / "settings.json",
                    stats_path=data_dir / "stats.json")
    return app.run(None)


if __name__ == "__main__":
    sys.exit(main())
