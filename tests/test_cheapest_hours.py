"""Tests for the shared cheapest-hours ranking and its use by both strategies."""

from datetime import datetime
from unittest.mock import MagicMock

import cheapest_hours as ch

import test_boiler_strategy as tb
import test_sessy_strategy as ts


def _prices(day_values):
    """{ISO: price} from {(day, hour): price}."""
    return {f"2024-06-{d:02d}T{h:02d}:00:00": p for (d, h), p in day_values.items()}


def _two_days(default=0.30, **overrides):
    values = {(d, h): default for d in (15, 16) for h in range(24)}
    values.update(overrides)
    return _prices(values)


class TestWindow:
    def test_window_starts_at_configured_hour(self):
        start, end = ch.price_window(datetime(2024, 6, 15, 14, 30), 2)
        assert start == datetime(2024, 6, 15, 2)
        assert end == datetime(2024, 6, 16, 2)

    def test_before_window_start_belongs_to_previous_window(self):
        start, end = ch.price_window(datetime(2024, 6, 16, 1, 0), 2)
        assert start == datetime(2024, 6, 15, 2)
        assert end == datetime(2024, 6, 16, 2)


class TestRank:
    def test_rank_one_is_cheapest(self):
        prices = _prices({(15, h): 0.30 for h in range(2, 24)} | {(15, 14): 0.01})
        assert ch.cheapest_hour_rank(prices, datetime(2024, 6, 15, 14), 2) == 1

    def test_night_hours_after_midnight_share_window_with_evening(self):
        # 00:00 on the 16th belongs to the window that started 02:00 on the 15th.
        prices = _two_days(**{})
        prices["2024-06-16T00:00:00"] = 0.01
        assert ch.cheapest_hour_rank(prices, datetime(2024, 6, 16, 0), 2) == 1
        assert ch.is_cheapest_hour(prices, datetime(2024, 6, 15, 12), 1, 2) is False

    def test_hour_before_window_start_is_not_in_next_window(self):
        prices = _two_days()
        prices["2024-06-15T01:00:00"] = 0.01
        # 15th 01:00 is in the previous window; ranking at 15th 14:00 ignores it.
        assert ch.is_cheapest_hour(prices, datetime(2024, 6, 15, 14), 1, 2) is False

    def test_no_prices_gives_none(self):
        assert ch.cheapest_hour_rank(None, datetime(2024, 6, 15, 14), 2) is None
        assert ch.is_cheapest_hour({}, datetime(2024, 6, 15, 14), 2, 2) is False

    def test_hour_cheap_when_rank_within_n(self):
        prices = _two_days(**{})
        prices["2024-06-15T10:00:00"] = 0.01
        prices["2024-06-15T11:00:00"] = 0.02
        now = datetime(2024, 6, 15, 11)
        assert ch.cheapest_hour_rank(prices, now, 2) == 2
        assert ch.is_cheapest_hour(prices, now, 2, 2) is True
        assert ch.is_cheapest_hour(prices, now, 1, 2) is False

    def test_cheapest_hours_chronological_and_empty_for_zero(self):
        prices = _two_days()
        prices["2024-06-15T20:00:00"] = 0.01
        prices["2024-06-15T05:00:00"] = 0.02
        now = datetime(2024, 6, 15, 9)
        assert ch.cheapest_hours(prices, now, 2, 2) == [
            datetime(2024, 6, 15, 5), datetime(2024, 6, 15, 20)
        ]
        assert ch.cheapest_hours(prices, now, 0, 2) == []


class TestStrategiesAgree:
    def test_battery_and_boiler_agree_across_midnight(self):
        prices = _two_days()
        prices["2024-06-16T00:00:00"] = 0.01   # tomorrow-midnight, same window
        prices["2024-06-15T14:00:00"] = 0.02
        for now in (datetime(2024, 6, 15, 14), datetime(2024, 6, 16, 0), datetime(2024, 6, 15, 9)):
            battery = ts.make_app()
            battery.datetime = MagicMock(return_value=now)
            battery._get_prices_dict = MagicMock(return_value=prices)
            boiler = tb.make_app()
            boiler.datetime = MagicMock(return_value=now)
            assert battery._is_cheapest_hour(2) == boiler._is_cheapest_hour(prices, 2)
