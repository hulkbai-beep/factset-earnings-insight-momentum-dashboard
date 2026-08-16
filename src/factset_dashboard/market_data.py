"""Fail-soft external market data used only as a dashboard overlay."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


YAHOO_SPX_PAGE_URL: Final = "https://finance.yahoo.com/quote/%5EGSPC/"
YAHOO_SPX_CHART_URL: Final = (
    "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
    "?range=5d&interval=1d&includePrePost=false"
)


class MarketDataError(RuntimeError):
    """Raised when an external quote is unavailable or malformed."""


@dataclass(frozen=True)
class MarketQuote:
    """A timestamped, source-labeled index quote."""

    symbol: str
    price: float
    previous_close: float | None
    currency: str
    as_of_utc: datetime
    exchange_timezone: str
    source: str = "Yahoo Finance"

    @property
    def day_change_pct(self) -> float | None:
        if self.previous_close is None or self.previous_close == 0:
            return None
        return (self.price / self.previous_close - 1.0) * 100.0

    def as_of_label(self) -> str:
        """Format the quote timestamp in its exchange timezone."""

        try:
            exchange_zone = ZoneInfo(self.exchange_timezone)
        except ZoneInfoNotFoundError:
            exchange_zone = timezone.utc
        local = self.as_of_utc.astimezone(exchange_zone)
        return local.strftime("%Y-%m-%d %I:%M %p %Z")


def _positive_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) and numeric > 0 else None


def parse_yahoo_chart_quote(payload: Mapping[str, Any]) -> MarketQuote:
    """Parse Yahoo's chart response without treating missing fields as zero."""

    try:
        chart = payload["chart"]
        if chart.get("error"):
            raise MarketDataError(f"Yahoo Finance returned an error: {chart['error']}")
        result = chart["result"][0]
        meta = result["meta"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MarketDataError("Yahoo Finance response is missing quote metadata") from exc

    timestamps = result.get("timestamp") or []
    quote_blocks = (result.get("indicators") or {}).get("quote") or []
    closes = quote_blocks[0].get("close") if quote_blocks else []
    daily_observations: list[tuple[int, float]] = []
    for raw_timestamp, raw_close in zip(timestamps, closes or []):
        close = _positive_float(raw_close)
        if close is None:
            continue
        try:
            observation_timestamp = int(raw_timestamp)
        except (TypeError, ValueError):
            continue
        daily_observations.append((observation_timestamp, close))

    price = _positive_float(meta.get("regularMarketPrice"))
    raw_as_of = meta.get("regularMarketTime")
    if price is None and daily_observations:
        raw_as_of, price = daily_observations[-1]
    if price is None:
        raise MarketDataError("Yahoo Finance response has no valid SPX price")

    if raw_as_of is None and daily_observations:
        raw_as_of = daily_observations[-1][0]
    try:
        as_of_utc = datetime.fromtimestamp(int(raw_as_of), tz=timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        raise MarketDataError("Yahoo Finance response has no valid quote timestamp") from exc

    previous_close = None
    if len(daily_observations) >= 2:
        previous_close = daily_observations[-2][1]
    if previous_close is None:
        previous_close = _positive_float(meta.get("regularMarketPreviousClose"))
    if previous_close is None:
        previous_close = _positive_float(meta.get("chartPreviousClose"))

    symbol = str(meta.get("symbol") or "^GSPC")
    if symbol != "^GSPC":
        raise MarketDataError(f"Expected ^GSPC but Yahoo Finance returned {symbol}")
    return MarketQuote(
        symbol=symbol,
        price=price,
        previous_close=previous_close,
        currency=str(meta.get("currency") or "USD"),
        as_of_utc=as_of_utc,
        exchange_timezone=str(meta.get("exchangeTimezoneName") or "America/New_York"),
    )


def fetch_yahoo_spx_quote(*, timeout_seconds: float = 6.0) -> MarketQuote:
    """Fetch Yahoo's latest available S&P 500 index quote.

    This adapter is an optional external overlay. It never writes to the
    canonical FactSet database and callers must handle ``MarketDataError``.
    """

    request = Request(
        YAHOO_SPX_CHART_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; local research dashboard)",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MarketDataError("Yahoo Finance SPX quote is temporarily unavailable") from exc
    return parse_yahoo_chart_quote(payload)
