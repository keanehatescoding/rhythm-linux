import pytest

from rhythm_linux.library import Track
from rhythm_linux.stats import FILTERS, TrackStats, filter_by_stats


def _t(n):
    return Track(path=f"/m/{n}.mp3", title=f"t{n}", artist="Ann", album="")


@pytest.fixture
def stats(tmp_path):
    s = TrackStats(tmp_path / "stats.json")
    s.load()
    s.set_rating("/m/1.mp3", 5)
    s.set_rating("/m/2.mp3", 3)
    s.set_rating("/m/3.mp3", 1)
    s.record_play("/m/2.mp3")
    return s


def _titles(tracks):
    return [t.title for t in tracks]


def test_all_tracks_keeps_everything(stats):
    tracks = [_t(1), _t(2), _t(3), _t(4)]
    assert _titles(filter_by_stats(tracks, stats, "All tracks")) == ["t1", "t2", "t3", "t4"]


def test_rated_3_plus(stats):
    tracks = [_t(1), _t(2), _t(3), _t(4)]
    assert _titles(filter_by_stats(tracks, stats, "Rated 3+ stars")) == ["t1", "t2"]


def test_rated_5_only(stats):
    tracks = [_t(1), _t(2), _t(3), _t(4)]
    assert _titles(filter_by_stats(tracks, stats, "Rated 5 stars")) == ["t1"]


def test_rated_1_plus_excludes_unrated(stats):
    tracks = [_t(1), _t(2), _t(3), _t(4)]
    assert _titles(filter_by_stats(tracks, stats, "Rated 1+ stars")) == ["t1", "t2", "t3"]


def test_never_played(stats):
    tracks = [_t(1), _t(2), _t(3), _t(4)]
    assert _titles(filter_by_stats(tracks, stats, "Never played")) == ["t1", "t3", "t4"]


def test_every_listed_filter_is_accepted(stats):
    for choice in FILTERS:
        filter_by_stats([_t(1)], stats, choice)


def test_unknown_filter_is_rejected(stats):
    with pytest.raises(ValueError):
        filter_by_stats([_t(1)], stats, "Bogus")
