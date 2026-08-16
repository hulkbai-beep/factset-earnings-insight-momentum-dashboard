from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from factset_dashboard.charts import valuation_scenario_range_chart
from factset_dashboard.market_data import MarketDataError, parse_yahoo_chart_quote
from factset_dashboard.metrics import calculate_valuation_scenarios


def _payload() -> dict[str, object]:
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": "^GSPC",
                        "currency": "USD",
                        "regularMarketPrice": 7785.76,
                        "regularMarketTime": 1786739967,
                        "exchangeTimezoneName": "America/New_York",
                        "chartPreviousClose": 7757.64,
                    },
                    "timestamp": [1786627800, 1786714200],
                    "indicators": {
                        "quote": [{"close": [7798.99, 7785.759765625]}]
                    },
                }
            ],
        }
    }


def test_yahoo_spx_quote_preserves_price_timestamp_and_prior_close() -> None:
    quote = parse_yahoo_chart_quote(_payload())

    assert quote.symbol == "^GSPC"
    assert quote.price == pytest.approx(7785.76)
    assert quote.previous_close == pytest.approx(7798.99)
    assert quote.day_change_pct == pytest.approx((7785.76 / 7798.99 - 1) * 100)
    assert quote.as_of_utc == datetime.fromtimestamp(1786739967, tz=timezone.utc)
    assert quote.as_of_label() == "2026-08-14 04:39 PM EDT"


def test_yahoo_quote_falls_back_to_latest_valid_daily_close() -> None:
    payload = _payload()
    result = payload["chart"]["result"][0]  # type: ignore[index]
    result["meta"].pop("regularMarketPrice")  # type: ignore[union-attr]
    result["meta"].pop("regularMarketTime")  # type: ignore[union-attr]

    quote = parse_yahoo_chart_quote(payload)

    assert quote.price == pytest.approx(7785.759765625)
    assert quote.as_of_utc == datetime.fromtimestamp(1786714200, tz=timezone.utc)


def test_yahoo_quote_rejects_missing_or_wrong_symbol_data() -> None:
    with pytest.raises(MarketDataError, match="missing quote metadata"):
        parse_yahoo_chart_quote({"chart": {"error": None, "result": []}})

    payload = _payload()
    result = payload["chart"]["result"][0]  # type: ignore[index]
    result["meta"]["symbol"] = "SPY"  # type: ignore[index]
    with pytest.raises(MarketDataError, match=r"Expected \^GSPC"):
        parse_yahoo_chart_quote(payload)


def test_valuation_chart_marks_latest_spx_level() -> None:
    scenarios = calculate_valuation_scenarios(
        pd.DataFrame(
            {
                "report_date": ["2026-08-07"],
                "period": ["CY2026"],
                "eps": [358.66],
            }
        ),
        periods=("CY2026",),
        as_of_date="2026-08-07",
        low_pe=19.0,
        base_pe=19.9,
        high_pe=20.0,
    )

    figure = valuation_scenario_range_chart(
        scenarios,
        current_index_level=7785.76,
    )

    assert len(figure.layout.shapes) == 1
    assert figure.layout.shapes[0].y0 == pytest.approx(7785.76)
    assert any("Latest SPX 7,785.76" in annotation.text for annotation in figure.layout.annotations)
