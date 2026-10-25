"""
Shared cheapest-hours ranking for the battery and boiler strategies.

Both strategies must agree on which hours are "cheapest", so the ranking lives
here once. Hours are ranked inside a 24h window that starts at window_start_h
and ends at the same hour the next day (default 02:00 to 02:00), so the night
cheap hours around midnight are not split across two calendar days.

An hour is "cheap" when its rank (1 = cheapest) is <= cheapest_hours_n.
"""

from datetime import datetime, timedelta


def _slot_start(raw):
    """Parse a timestamp to a naive wall-clock datetime, or None."""
    try:
        return datetime.fromisoformat(str(raw)).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _hourly_prices(prices):
    """
    Average the price slots per clock hour: {hour_start: price}.

    Source is the Sessy price sensor's energy_prices attribute:
    dict {ISO_timestamp: price}. Anything else yields no prices.
    """
    if not isinstance(prices, dict):
        return {}

    buckets = {}
    for raw, price in prices.items():
        start = _slot_start(raw)
        if start is None:
            continue
        try:
            value = float(price)
        except (TypeError, ValueError):
            continue
        buckets.setdefault(start.replace(minute=0, second=0, microsecond=0), []).append(value)
    return {hour: sum(v) / len(v) for hour, v in buckets.items()}


def price_window(now, window_start_h):
    """The 24h window [start, end) that contains `now`."""
    start = now.replace(hour=window_start_h, minute=0, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    return start, start + timedelta(days=1)


def ranked_hours(prices, now, window_start_h):
    """Hour starts of the current window, cheapest first (ties: earliest first)."""
    start, end = price_window(now, window_start_h)
    hourly = _hourly_prices(prices)
    in_window = [(price, hour) for hour, price in hourly.items() if start <= hour < end]
    in_window.sort()
    return [hour for _, hour in in_window]


def cheapest_hour_rank(prices, now, window_start_h):
    """Rank (1 = cheapest) of the current hour in its window, or None if unpriced."""
    current = now.replace(minute=0, second=0, microsecond=0)
    ranking = ranked_hours(prices, now, window_start_h)
    if current not in ranking:
        return None
    return ranking.index(current) + 1


def is_cheapest_hour(prices, now, n, window_start_h):
    """True when the current hour's rank is within the n cheapest of its window."""
    rank = cheapest_hour_rank(prices, now, window_start_h)
    return rank is not None and rank <= int(n)


def cheapest_hours(prices, now, n, window_start_h):
    """The n cheapest hour starts of the current window, in chronological order."""
    if int(n) <= 0:
        return []
    return sorted(ranked_hours(prices, now, window_start_h)[: int(n)])
