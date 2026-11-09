"""Tests for the shared cheapest-hours ranking and its use by both strategies."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import cheapest_hours as ch
import pytest
import yaml

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


class TestPriceThreshold:
    def test_threshold_uses_hourly_averages_inside_current_window(self):
        prices = {
            "2024-06-15T01:00:00": -1.0,
            "2024-06-15T10:00:00": 0.02,
            "2024-06-15T10:15:00": 0.18,
            "2024-06-15T11:00:00": 0.08,
            "2024-06-16T00:00:00": 0.20,
            "2024-06-16T02:00:00": -2.0,
        }
        assert ch.cheapest_hours_price_threshold(prices, datetime(2024, 6, 15, 14), 2, 2) == pytest.approx(0.10)

    def test_no_selection_has_no_threshold(self):
        now = datetime(2024, 6, 15, 14)
        assert ch.cheapest_hours_price_threshold(None, now, 2, 2) is None
        assert ch.cheapest_hours_price_threshold({}, now, 2, 2) is None
        assert ch.cheapest_hours_price_threshold(_two_days(), now, 0, 2) is None

    def test_partial_forecast_and_ties_keep_existing_selection(self):
        now = datetime(2024, 6, 15, 14)
        prices = _prices({(15, 10): -0.10, (15, 11): -0.10, (15, 12): -0.10})
        assert ch.cheapest_hours_price_threshold(prices, now, 2, 2) == -0.10
        assert len(ch.cheapest_hours(prices, now, 2, 2)) == 2
        assert ch.cheapest_hours_price_threshold(prices, now, 5, 2) == -0.10


class TestMaxPriceAfterNow:
    def test_highest_later_hour_up_to_window_end(self):
        prices = _two_days()
        prices["2024-06-15T20:00:00"] = 0.50
        prices["2024-06-16T01:00:00"] = 0.60   # still in window (ends 02:00)
        prices["2024-06-16T03:00:00"] = 0.90   # next window — ignored
        assert ch.max_price_after_now(prices, datetime(2024, 6, 15, 14, 30), 2) == 0.60

    def test_current_and_past_hours_ignored(self):
        prices = _two_days(default=0.10)
        prices["2024-06-15T14:00:00"] = 0.90
        prices["2024-06-15T10:00:00"] = 0.80
        assert ch.max_price_after_now(prices, datetime(2024, 6, 15, 14), 2) == 0.10

    def test_none_when_no_later_prices(self):
        assert ch.max_price_after_now(None, datetime(2024, 6, 15, 14), 2) is None
        prices = {"2024-06-16T01:00:00": 0.20}
        assert ch.max_price_after_now(prices, datetime(2024, 6, 16, 1), 2) is None


AMS = ZoneInfo("Europe/Amsterdam")

# Live sensor data of 2026-11-09 (CET, UTC+1): keys are UTC with an offset.
UTC_PRICES_2026_11_09 = {
    "2026-11-09T15:00:00+00:00": 0.31,     # 16:00 CET
    "2026-11-09T16:00:00+00:00": 0.60945,  # 17:00 CET
    "2026-11-09T17:00:00+00:00": 0.45,     # 18:00 CET
    "2026-11-09T18:00:00+00:00": 0.40,     # 19:00 CET
    "2026-11-09T19:00:00+00:00": 0.37398,  # 20:00 CET
    "2026-11-09T20:00:00+00:00": 0.32399,  # 21:00 CET
    "2026-11-09T21:00:00+00:00": 0.28,     # 22:00 CET
}


class TestUtcPriceKeys:
    def test_current_price_from_utc_keys_in_winter(self):
        now = datetime(2026, 11, 9, 17, 30)
        assert ch.price_at(UTC_PRICES_2026_11_09, now, AMS) == pytest.approx(0.60945)

    def test_evening_peak_from_utc_keys_in_winter(self):
        peak = ch.max_price_between(
            UTC_PRICES_2026_11_09, datetime(2026, 11, 9, 20), datetime(2026, 11, 9, 22), AMS)
        assert peak == pytest.approx(0.37398)

    def test_afternoon_guard_blocks_charging_at_todays_prices(self):
        # 17:00 CET: price 0.609, evening peak 0.374, margin 0.25 → skip.
        peak = ch.max_price_between(
            UTC_PRICES_2026_11_09, datetime(2026, 11, 9, 20), datetime(2026, 11, 9, 22), AMS)
        price = ch.price_at(UTC_PRICES_2026_11_09, datetime(2026, 11, 9, 17, 30), AMS)
        assert ch.beats_by_margin(peak, price, 0.25) is False

    def test_guard_fails_closed_without_later_price(self):
        assert ch.beats_by_margin(None, 0.20, 0.05) is False

    def test_guard_charges_when_spread_equals_margin(self):
        assert ch.beats_by_margin(0.50, 0.25, 0.25) is True

    def test_utc_keys_in_summer_shift_two_hours(self):
        prices = {"2024-06-15T18:00:00+00:00": 0.42}   # 20:00 CEST
        assert ch.price_at(prices, datetime(2024, 6, 15, 20, 10), AMS) == pytest.approx(0.42)
        assert ch.price_at(prices, datetime(2024, 6, 15, 18, 10), AMS) is None

    def test_non_dict_prices_yield_nothing(self):
        assert ch.price_at([0.1, 0.2], datetime(2024, 6, 15, 0), AMS) is None

    def test_cheapest_hours_ranked_in_local_time(self):
        # Cheapest UTC slots 02:00/03:00 are 03:00/04:00 CET.
        prices = {f"2026-11-09T{h:02d}:00:00+00:00": 0.30 for h in range(1, 23)}
        prices["2026-11-09T02:00:00+00:00"] = 0.05
        prices["2026-11-09T03:00:00+00:00"] = 0.06
        now = datetime(2026, 11, 9, 12)
        assert ch.cheapest_hours(prices, now, 2, 2, tz=AMS) == [
            datetime(2026, 11, 9, 3), datetime(2026, 11, 9, 4)
        ]
        assert ch.is_cheapest_hour(prices, datetime(2026, 11, 9, 3), 2, 2, tz=AMS) is True
        assert ch.is_cheapest_hour(prices, datetime(2026, 11, 9, 2), 2, 2, tz=AMS) is False

    def test_contiguous_hours_follow_local_time(self):
        prices = {
            "2026-11-09T02:00:00+00:00": -0.20,  # 03:00 CET
            "2026-11-09T03:00:00+00:00": -0.15,  # 04:00 CET
            "2026-11-09T04:00:00+00:00": 0.10,   # 05:00 CET
        }
        now = datetime(2026, 11, 9, 3, 30)
        assert ch.contiguous_hours(prices, now, -0.10, above=False, tz=AMS) == pytest.approx(1.5)

    def test_contiguous_hours_default_to_one_without_run(self):
        now = datetime(2026, 11, 9, 3, 30)
        assert ch.contiguous_hours(None, now, -0.10, above=False, tz=AMS) == 1.0


class TestAppTimezone:
    def test_tzinfo_passes_through(self):
        app = MagicMock(get_timezone=MagicMock(return_value=AMS))
        assert ch.app_timezone(app) is AMS

    def test_name_string_is_resolved(self):
        app = MagicMock(get_timezone=MagicMock(return_value="Europe/London"))
        assert ch.app_timezone(app) == ZoneInfo("Europe/London")

    def test_unavailable_falls_back_to_amsterdam(self):
        app = MagicMock(get_timezone=MagicMock(side_effect=AttributeError))
        assert ch.app_timezone(app) == AMS


class TestStrategiesAgree:
    def test_apps_yaml_gives_both_apps_the_same_window(self):
        config = yaml.safe_load(Path("files/apps.yaml").read_text(encoding="utf-8"))
        assert config["sessy_strategy"]["cheapest_window_start_h"] == \
            config["boiler_strategy"]["cheapest_window_start_h"]

    def test_default_window_start_is_shared(self):
        battery = ts.make_app()
        boiler = tb.make_app()
        assert battery.cheapest_window_start_h == ch.DEFAULT_WINDOW_START_H
        assert boiler.cheapest_window_start_h == ch.DEFAULT_WINDOW_START_H
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
