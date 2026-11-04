import random

from rhythm_linux.library import Track
from rhythm_linux.queue import PlaybackQueue


def _t(n):
    return Track(path=f"/m/{n}.mp3", title=f"t{n}", artist="", album="")


def test_upcoming_lists_tracks_after_current():
    tracks = [_t(i) for i in range(4)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[1])
    assert [t.title for t in q.upcoming()] == ["t2", "t3"]


def test_upcoming_is_empty_at_the_end_and_for_empty_queue():
    q = PlaybackQueue(random.Random(0))
    assert q.upcoming() == []
    q.set_tracks([_t(0), _t(1)], start=None)
    q.next()
    assert q.upcoming() == []


def test_jump_moves_current_and_skips_tracks_before_it():
    tracks = [_t(i) for i in range(4)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[0])
    assert q.jump(1).title == "t2"
    assert q.current().title == "t2"
    assert [t.title for t in q.upcoming()] == ["t3"]


def test_jump_out_of_range_changes_nothing():
    tracks = [_t(0), _t(1)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[0])
    assert q.jump(5) is None
    assert q.current().title == "t0"
