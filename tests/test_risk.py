from forex_bot.risk import PositionSizer


def test_normalize_volume_rounds_down_to_step() -> None:
    assert PositionSizer._normalize_volume(0.137, 0.01, 100.0, 0.01) == 0.13


def test_normalize_volume_respects_bounds() -> None:
    assert PositionSizer._normalize_volume(0.001, 0.01, 100.0, 0.01) == 0.01
    assert PositionSizer._normalize_volume(500.0, 0.01, 100.0, 0.01) == 100.0
