import pytest

from rhythm_linux.player import crossfade_levels
from rhythm_linux.settings import Settings


def test_levels_at_start_are_outgoing_full_incoming_silent():
    assert crossfade_levels(0.0, 1.0) == pytest.approx((1.0, 0.0))


def test_levels_at_end_are_outgoing_silent_incoming_full():
    assert crossfade_levels(1.0, 0.8) == pytest.approx((0.0, 0.8))


def test_levels_halfway_are_equal_and_scale_with_volume():
    out_vol, in_vol = crossfade_levels(0.5, 0.6)
    assert out_vol == pytest.approx(0.3)
    assert in_vol == pytest.approx(0.3)


def test_progress_is_clamped_outside_zero_to_one():
    assert crossfade_levels(-0.5, 1.0) == pytest.approx((1.0, 0.0))
    assert crossfade_levels(2.0, 1.0) == pytest.approx((0.0, 1.0))


def test_crossfade_setting_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings(path)
    s.load()
    assert s.crossfade == 0.0
    s.crossfade = 6
    again = Settings(path)
    again.load()
    assert again.crossfade == 6.0


def test_crossfade_setting_is_clamped(tmp_path):
    s = Settings(tmp_path / "settings.json")
    s.load()
    s.crossfade = 99
    assert s.crossfade == 12.0
    s.crossfade = -3
    assert s.crossfade == 0.0
