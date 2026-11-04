import random

from rhythm_linux.library import Track
from rhythm_linux.queue import REPEAT_ALL, REPEAT_OFF, REPEAT_ONE, PlaybackQueue


def tracks(n):
    return [Track(path=f"/m/{i}.mp3", title=f"t{i}", artist="", album="") for i in range(n)]


def test_linear_order_and_stop_at_end():
    ts = tracks(3)
    q = PlaybackQueue()
    q.set_tracks(ts, start=ts[0])
    assert [q.current().title, q.next().title, q.next().title] == ["t0", "t1", "t2"]
    assert q.next() is None


def test_previous_stays_at_start_without_repeat():
    ts = tracks(3)
    q = PlaybackQueue()
    q.set_tracks(ts, start=ts[0])
    assert q.previous().title == "t0"
    q.next()
    assert q.previous().title == "t0"


def test_repeat_all_wraps_forward_and_backward():
    ts = tracks(2)
    q = PlaybackQueue()
    q.set_tracks(ts, start=ts[1])
    q.cycle_repeat()
    assert q.repeat == REPEAT_ALL
    assert q.next().title == "t0"
    assert q.previous().title == "t1"


def test_repeat_one_keeps_same_track():
    ts = tracks(3)
    q = PlaybackQueue()
    q.set_tracks(ts, start=ts[1])
    q.cycle_repeat()
    q.cycle_repeat()
    assert q.repeat == REPEAT_ONE
    assert q.next().title == "t1" and q.next().title == "t1"


def test_repeat_cycles_off_all_one_off():
    q = PlaybackQueue()
    assert [q.cycle_repeat() for _ in range(3)] == [REPEAT_ALL, REPEAT_ONE, REPEAT_OFF]


def test_shuffle_plays_every_track_once_starting_with_chosen_track():
    ts = tracks(20)
    q = PlaybackQueue(rng=random.Random(1))
    q.set_shuffle(True)
    q.set_tracks(ts, start=ts[7])
    played = [q.current()]
    while (t := q.next()) is not None:
        played.append(t)
    assert played[0] == ts[7]
    assert sorted(t.path for t in played) == sorted(t.path for t in ts)
    assert [t.path for t in played] != [t.path for t in ts]  # actually shuffled


def test_turning_shuffle_on_keeps_current_track():
    ts = tracks(5)
    q = PlaybackQueue(rng=random.Random(3))
    q.set_tracks(ts, start=ts[2])
    q.set_shuffle(True)
    assert q.current() == ts[2]


def test_repeat_all_with_shuffle_reshuffles_and_keeps_going():
    ts = tracks(4)
    q = PlaybackQueue(rng=random.Random(5))
    q.set_shuffle(True)
    q.set_tracks(ts, start=ts[0])
    q.cycle_repeat()
    seen = [q.current()]
    for _ in range(8):
        seen.append(q.next())
    assert all(t is not None for t in seen)
    assert {t.path for t in seen[:4]} == {t.path for t in ts}
