"""
Shared cheapest-hours ranking for the battery and boiler strategies.

Both strategies must agree on which hours are "cheapest", so the ranking lives
here once. Hours are ranked inside a 24h window that starts at window_start_h
and ends at the same hour the next day (default 02:00 to 02:00), so the night
cheap hours around midnight are not split across two calendar days.

An hour is "cheap" when its rank (1 = cheapest) is <= cheapest_hours_n.
"""

from datetime import datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Europe/Amsterdam"
# Shared by the battery and boiler strategies: the price window runs from this
# local hour to the same hour the next day. Override per app only together.
DEFAULT_WINDOW_START_H = 2


def app_timezone(app):
    """
    Local timezone of an AppDaemon app. get_timezone() returns a tzinfo on
    recent AppDaemon and a name string on older versions; anything unusable
    falls back to DEFAULT_TZ (never the container's system zone, often UTC).
    """
    try:
        tz = app.get_timezone()
        if isinstance(tz, str):
            tz = ZoneInfo(tz)
    except Exception:
        tz = None
    return tz if isinstance(tz, tzinfo) else ZoneInfo(DEFAULT_TZ)


def _slot_start(raw, tz=None):
    """
    Parse a timestamp to a naive local wall-clock datetime, or None.

    Keys with an offset (the Sessy sensor sends UTC, e.g. "...T16:00:00+00:00")
    are converted to tz first; naive keys are taken as local time already.
    """
    try:
        start = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if start.tzinfo is not None:
        start = start.astimezone(tz)
    return start.replace(tzinfo=None)


def _hourly_prices(prices, tz=None):
    """
    Average the price slots per local clock hour: {hour_start: price}.

    Source is the Sessy price sensor's energy_prices attribute:
    dict {ISO_timestamp: price}. Anything else yields no prices.
    """
    if not isinstance(prices, dict):
        return {}

    buckets = {}
    for raw, price in prices.items():
        start = _slot_start(raw, tz)
        if start is None:
            continue
        try:
            value = float(price)
        except (TypeError, ValueError):
            continue
        buckets.setdefault(start.replace(minute=0, second=0, microsecond=0), []).append(value)
    return {hour: sum(v) / len(v) for hour, v in buckets.items()}


def _hour_of(now):
    return now.replace(minute=0, second=0, microsecond=0)


def price_at(prices, now, tz=None):
    """Price of the local clock hour containing `now`, or None if unpriced."""
    return _hourly_prices(prices, tz).get(_hour_of(now))


def max_price_between(prices, start, end, tz=None):
    """Highest hourly price for local hour starts in [start, end), or None."""
    values = [p for hour, p in _hourly_prices(prices, tz).items() if start <= hour < end]
    return max(values) if values else None


def contiguous_hours(prices, now, threshold, above, tz=None):
    """
    Fractional hours remaining (from now) that the price stays past threshold:
    above it when above=True, below it when above=False. Counts whole hourly
    slots from the current hour, stops at the first hour that crosses back (or
    is unpriced), then subtracts the elapsed part of the current hour.
    Returns 1.0 when there is no such run, so callers never divide by zero.
    """
    hourly = _hourly_prices(prices, tz)
    cursor = _hour_of(now)
    count = 0
    for _ in range(48):
        price = hourly.get(cursor)
        if price is None or not ((price > threshold) if above else (price < threshold)):
            break
        count += 1
        cursor += timedelta(hours=1)
    if count == 0:
        return 1.0
    elapsed_h = (now - _hour_of(now)).total_seconds() / 3600.0
    return max(count - elapsed_h, 0.0)


def beats_by_margin(later_price, price, margin):
    """
    Break-even guard: True when later_price exceeds price by at least margin.
    Missing later price data never justifies charging (fail-closed).
    """
    if later_price is None or price is None:
        return False
    return (later_price - price) >= margin


def price_window(now, window_start_h):
    """The 24h window [start, end) that contains `now`."""
    start = now.replace(hour=window_start_h, minute=0, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    return start, start + timedelta(days=1)


def ranked_hours(prices, now, window_start_h, tz=None):
    """Hour starts of the current window, cheapest first (ties: earliest first)."""
    start, end = price_window(now, window_start_h)
    hourly = _hourly_prices(prices, tz)
    in_window = [(price, hour) for hour, price in hourly.items() if start <= hour < end]
    in_window.sort()
    return [hour for _, hour in in_window]


def cheapest_hour_rank(prices, now, window_start_h, tz=None):
    """Rank (1 = cheapest) of the current hour in its window, or None if unpriced."""
    current = _hour_of(now)
    ranking = ranked_hours(prices, now, window_start_h, tz)
    if current not in ranking:
        return None
    return ranking.index(current) + 1


def is_cheapest_hour(prices, now, n, window_start_h, tz=None):
    """True when the current hour's rank is within the n cheapest of its window."""
    rank = cheapest_hour_rank(prices, now, window_start_h, tz)
    return rank is not None and rank <= int(n)


def max_price_after_now(prices, now, window_start_h, tz=None):
    """Highest hourly price after the current hour, up to the window end, or None."""
    _, end = price_window(now, window_start_h)
    current = _hour_of(now)
    later = [price for hour, price in _hourly_prices(prices, tz).items() if current < hour < end]
    return max(later) if later else None


def cheapest_hours(prices, now, n, window_start_h, tz=None):
    """The n cheapest hour starts of the current window, in chronological order."""
    if int(n) <= 0:
        return []
    return sorted(ranked_hours(prices, now, window_start_h, tz)[: int(n)])


def cheapest_hours_price_threshold(prices, now, n, window_start_h, tz=None):
    """Highest hourly average among the selected cheapest hours, or None."""
    selected = cheapest_hours(prices, now, n, window_start_h, tz)
    hourly = _hourly_prices(prices, tz)
    return max((hourly[hour] for hour in selected), default=None)