import random

from rhythm_linux.library import Track
from rhythm_linux.queue import PlaybackQueue


def _t(n):
    return Track(path=f"/m/{n}.mp3", title=f"t{n}", artist="", album="")


def _titles(q):
    return [t.title for t in q.upcoming()]


def test_remove_upcoming_drops_that_track_only():
    tracks = [_t(i) for i in range(4)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[0])
    assert q.remove_upcoming(0) is True
    assert _titles(q) == ["t2", "t3"]
    assert q.current().title == "t0"


def test_removed_track_does_not_come_back_on_repeat_all():
    tracks = [_t(i) for i in range(3)]
    q = PlaybackQueue(random.Random(0))
    q.cycle_repeat()  # repeat all
    q.set_tracks(tracks, start=tracks[0])
    q.remove_upcoming(0)  # drop t1
    assert q.next().title == "t2"
    assert q.next().title == "t0"  # wraps without t1
    assert q.next().title == "t2"


def test_remove_out_of_range_changes_nothing():
    tracks = [_t(0), _t(1)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[1])
    assert q.remove_upcoming(0) is False
    assert q.current().title == "t1"


def test_move_upcoming_swaps_neighbours():
    tracks = [_t(i) for i in range(4)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[0])
    assert q.move_upcoming(1, -1) is True  # t2 moves above t1
    assert _titles(q) == ["t2", "t1", "t3"]
    # the new order survives a trip to the end and repeat
    q.cycle_repeat()
    assert [q.next().title for _ in range(3)] == ["t2", "t1", "t3"]


def test_move_upcoming_refuses_to_leave_the_queue():
    tracks = [_t(i) for i in range(3)]
    q = PlaybackQueue(random.Random(0))
    q.set_tracks(tracks, start=tracks[0])
    assert q.move_upcoming(0, -1) is False  # would swap with the current track
    assert q.move_upcoming(1, 1) is False   # off the end
    assert _titles(q) == ["t1", "t2"]
