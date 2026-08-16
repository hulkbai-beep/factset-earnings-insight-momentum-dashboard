from __future__ import annotations

import pandas as pd
import pytest

from factset_dashboard.metrics import calculate_eps_momentum


def _eps_frame(dates: list[str], values: list[float | None]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "report_id": range(1, len(dates) + 1),
            "report_date": dates,
            "period": "CY2026",
            "period_type": "calendar_year",
            "eps": values,
        }
    )


def _at(result: pd.DataFrame, report_date: str) -> pd.Series:
    return result.loc[result["report_date"].eq(pd.Timestamp(report_date))].iloc[0]


def test_05_previous_publication_eps_revision_calculation() -> None:
    result = calculate_eps_momentum(
        _eps_frame(["2026-01-02", "2026-01-09"], [100.0, 110.0])
    )
    current = _at(result, "2026-01-09")

    assert current["comparison_1p_date"] == pd.Timestamp("2026-01-02")
    assert current["change_1p_pct"] == pytest.approx(10.0)


def test_06_four_week_revision_uses_calendar_date_anchor() -> None:
    result = calculate_eps_momentum(
        _eps_frame(
            ["2026-01-02", "2026-01-16", "2026-02-13"],
            [100.0, 105.0, 121.0],
        )
    )
    current = _at(result, "2026-02-13")

    assert current["anchor_4w_date"] == pd.Timestamp("2026-01-16")
    assert current["comparison_4w_date"] == pd.Timestamp("2026-01-16")
    assert current["change_4w_pct"] == pytest.approx((121.0 / 105.0 - 1) * 100)


def test_07_thirteen_week_revision_uses_calendar_date_anchor() -> None:
    result = calculate_eps_momentum(
        _eps_frame(
            ["2026-01-02", "2026-02-06", "2026-03-06", "2026-04-03"],
            [100.0, 108.0, 115.0, 125.0],
        )
    )
    current = _at(result, "2026-04-03")

    assert current["anchor_13w_date"] == pd.Timestamp("2026-01-02")
    assert current["comparison_13w_date"] == pd.Timestamp("2026-01-02")
    assert current["change_13w_pct"] == pytest.approx(25.0)


def test_08_irregular_publication_dates_do_not_use_row_offsets() -> None:
    result = calculate_eps_momentum(
        _eps_frame(
            [
                "2026-01-08",
                "2026-01-29",
                "2026-02-12",
                "2026-02-20",
                "2026-02-28",
                "2026-03-27",
            ],
            [100.0, 110.0, 125.0, 140.0, 150.0, 160.0],
        )
    )
    current = _at(result, "2026-03-27")

    assert current["anchor_4w_date"] == pd.Timestamp("2026-02-27")
    assert current["comparison_4w_date"] == pd.Timestamp("2026-02-20")
    assert current["change_4w_pct"] == pytest.approx((160.0 / 140.0 - 1) * 100)


def test_09_missing_or_stale_historical_comparison_returns_na() -> None:
    result = calculate_eps_momentum(
        _eps_frame(["2026-01-01", "2026-02-20"], [100.0, 120.0])
    )
    current = _at(result, "2026-02-20")

    assert current["anchor_4w_date"] == pd.Timestamp("2026-01-23")
    assert pd.isna(current["comparison_4w_date"])
    assert pd.isna(current["change_4w_pct"])
    assert pd.isna(current["comparison_13w_date"])
    assert pd.isna(current["change_13w_pct"])


def test_null_intermediate_observation_falls_back_to_latest_valid_value() -> None:
    result = calculate_eps_momentum(
        _eps_frame(
            ["2026-03-12", "2026-03-19", "2026-04-17"],
            [100.0, None, 110.0],
        )
    )
    current = _at(result, "2026-04-17")

    assert current["comparison_1p_date"] == pd.Timestamp("2026-03-12")
    assert current["comparison_4w_date"] == pd.Timestamp("2026-03-12")
    assert current["change_1p_pct"] == pytest.approx(10.0)
    assert current["change_4w_pct"] == pytest.approx(10.0)
