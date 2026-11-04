from datetime import datetime

import pytest

from rhythm_linux.library import Track
from rhythm_linux.stats import TrackStats, sort_by_stats


def _t(n, artist="Ann"):
    return Track(path=f"/m/{n}.mp3", title=f"t{n}", artist=artist, album="")


@pytest.fixture
def stats(tmp_path):
    s = TrackStats(tmp_path / "stats.json")
    s.load()
    return s


def test_sort_by_rating_highest_first_then_title(stats):
    tracks = [_t(1), _t(2), _t(3)]
    stats.set_rating("/m/2.mp3", 5)
    stats.set_rating("/m/3.mp3", 2)
    assert [t.title for t in sort_by_stats(tracks, stats, "Rating")] == ["t2", "t3", "t1"]


def test_sort_by_most_played_highest_first(stats):
    tracks = [_t(1), _t(2), _t(3)]
    stats.record_play("/m/3.mp3", when=datetime(2026, 1, 1))
    stats.record_play("/m/3.mp3", when=datetime(2026, 1, 2))
    stats.record_play("/m/1.mp3", when=datetime(2026, 1, 3))
    assert [t.title for t in sort_by_stats(tracks, stats, "Most played")] == ["t3", "t1", "t2"]


def test_unknown_stats_sort_is_rejected(stats):
    with pytest.raises(ValueError):
        sort_by_stats([_t(1)], stats, "Artist")
