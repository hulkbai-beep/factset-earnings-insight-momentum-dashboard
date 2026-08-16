from __future__ import annotations

import pandas as pd
import pytest

from factset_dashboard.metrics import (
    calculate_valuation_scenarios,
    default_valuation_multiples,
)


def test_observed_valuation_references_become_sorted_defaults() -> None:
    index_metrics = pd.DataFrame(
        {
            "report_date": ["2026-08-07"],
            "forward_12m_pe": [20.0],
            "forward_12m_pe_5y_avg": [19.9],
            "forward_12m_pe_10y_avg": [19.0],
        }
    )

    assert default_valuation_multiples(
        index_metrics, as_of_date="2026-08-07"
    ) == pytest.approx((19.0, 19.9, 20.0))


def test_calendar_year_eps_times_pe_produces_index_level_range() -> None:
    eps = pd.DataFrame(
        {
            "report_date": ["2026-08-07", "2026-08-07"],
            "period": ["CY2026", "CY2027"],
            "eps": [358.66, 405.17],
        }
    )

    result = calculate_valuation_scenarios(
        eps,
        periods=("CY2026", "CY2027"),
        as_of_date="2026-08-07",
        low_pe=19.0,
        base_pe=19.9,
        high_pe=20.0,
    ).set_index("period")

    assert result.loc["CY2026", "low_index_level"] == pytest.approx(6814.54)
    assert result.loc["CY2026", "base_index_level"] == pytest.approx(7137.334)
    assert result.loc["CY2026", "high_index_level"] == pytest.approx(7173.2)
    assert result.loc["CY2027", "low_index_level"] == pytest.approx(7698.23)
    assert result.loc["CY2027", "base_index_level"] == pytest.approx(8062.883)
    assert result.loc["CY2027", "high_index_level"] == pytest.approx(8103.4)


def test_missing_eps_stays_missing_and_multiples_must_be_ordered() -> None:
    eps = pd.DataFrame(
        {
            "report_date": ["2026-08-07"],
            "period": ["CY2026"],
            "eps": [358.66],
        }
    )
    result = calculate_valuation_scenarios(
        eps,
        periods=("CY2026", "CY2027"),
        as_of_date="2026-08-07",
        low_pe=19.0,
        base_pe=19.9,
        high_pe=20.0,
    ).set_index("period")

    assert pd.isna(result.loc["CY2027", "eps"])
    assert pd.isna(result.loc["CY2027", "base_index_level"])
    with pytest.raises(ValueError, match="low <= base <= high"):
        calculate_valuation_scenarios(
            eps,
            periods=("CY2026",),
            as_of_date="2026-08-07",
            low_pe=21.0,
            base_pe=20.0,
            high_pe=19.0,
        )
