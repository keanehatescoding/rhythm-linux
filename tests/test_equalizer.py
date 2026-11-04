from rhythm_linux.equalizer import BAND_COUNT, DEFAULT_PRESET, MAX_GAIN_DB, PRESETS, clamp_gains, gains_for


def test_every_preset_has_ten_bands_within_range():
    for name, gains in PRESETS.items():
        assert len(gains) == BAND_COUNT, name
        assert all(abs(g) <= MAX_GAIN_DB for g in gains), name


def test_flat_is_all_zero():
    assert gains_for("Flat") == [0.0] * BAND_COUNT


def test_unknown_name_falls_back_to_default():
    assert gains_for("Nonsense") == PRESETS[DEFAULT_PRESET]


def test_gains_for_returns_a_copy():
    gains_for("Vocal").clear()
    assert len(gains_for("Vocal")) == BAND_COUNT


def test_clamp_limits_out_of_range_values():
    assert clamp_gains([30, -30, 3]) == [MAX_GAIN_DB, -MAX_GAIN_DB, 3.0]
