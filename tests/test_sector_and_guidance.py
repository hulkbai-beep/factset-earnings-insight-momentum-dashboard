from __future__ import annotations

from pathlib import Path

import pandas as pd

from factset_dashboard.metrics import (
    add_guidance_metrics,
    calculate_sector_index_spreads,
    detect_horizon_rolls,
    horizon_roll_dates,
)
from factset_dashboard.queries import load_dashboard_bundle


def test_10_horizon_roll_is_detected() -> None:
    leadership = pd.DataFrame(
        {
            "report_date": [
                "2026-04-02",
                "2026-04-02",
                "2026-04-17",
                "2026-04-17",
                "2026-04-24",
                "2026-04-24",
            ],
            "sector": ["Energy", "Technology"] * 3,
            "near_year_period": ["CY2025"] * 2 + ["CY2026"] * 4,
            "far_year_period": ["CY2026"] * 2 + ["CY2027"] * 4,
            "horizon_roll_flag": [0, 0, 1, 1, 0, 0],
        }
    )

    horizons = detect_horizon_rolls(leadership)
    rolls = horizon_roll_dates(leadership)

    assert horizons["horizon_roll_flag"].tolist() == [False, True, False]
    assert horizons["horizon_regime_id"].tolist() == [0, 1, 1]
    assert rolls == (pd.Timestamp("2026-04-17"),)


def test_11_sector_relative_growth_matches_report_and_period() -> None:
    sector = pd.DataFrame(
        {
            "report_id": [1, 1, 2],
            "period": ["CY2026", "CY2027", "CY2026"],
            "sector": ["Energy", "Energy", "Energy"],
            "earnings_growth_pct": [15.0, 30.0, 50.0],
        }
    )
    index = pd.DataFrame(
        {
            "report_id": [1, 1, 2],
            "period": ["CY2026", "CY2027", "CY2026"],
            "earnings_growth_pct": [10.0, 100.0, 20.0],
        }
    )

    result = calculate_sector_index_spreads(
        sector,
        index,
        metrics="earnings_growth_pct",
    )

    assert result["earnings_growth_spread_pp"].tolist() == [5.0, -70.0, 30.0]


def test_12_missing_sector_observations_are_not_treated_as_zero() -> None:
    sector = pd.DataFrame(
        {
            "report_id": [1, 1],
            "period": ["CY2026", "CY2026"],
            "sector": ["Information Technology", "Energy"],
            "earnings_growth_pct": [None, 5.0],
        }
    )
    index = pd.DataFrame(
        {
            "report_id": [1],
            "period": ["CY2026"],
            "earnings_growth_pct": [10.0],
        }
    )

    result = calculate_sector_index_spreads(
        sector,
        index,
        metrics="earnings_growth_pct",
    ).set_index("sector")

    assert pd.isna(
        result.loc["Information Technology", "earnings_growth_spread_pp"]
    )
    assert result.loc["Energy", "earnings_growth_spread_pp"] == -5.0
    assert "Utilities" not in result.index


def test_13_missing_guidance_counts_are_not_treated_as_zero() -> None:
    guidance = pd.DataFrame(
        {
            "positive_count": [None, 2],
            "negative_count": [3, 6],
            "positive_pct": [None, None],
            "negative_pct": [None, None],
        }
    )

    result = add_guidance_metrics(guidance)

    assert pd.isna(result.loc[0, "positive_count"])
    assert not bool(result.loc[0, "guidance_counts_complete"])
    assert pd.isna(result.loc[0, "guidance_total_count"])
    assert pd.isna(result.loc[0, "guidance_count_balance"])
    assert pd.isna(result.loc[0, "guidance_balance_pct"])
    assert result.loc[1, "guidance_balance_pct"] == -50.0
    assert result.loc[1, "guidance_balance_source"] == "DERIVED_FROM_COUNTS"


def test_14_leadership_quadrant_returns_one_row_per_available_sector(
    phase3_db: Path,
) -> None:
    leadership = load_dashboard_bundle(phase3_db)["sector_leadership"]
    latest = leadership.loc[
        leadership["report_date"].eq(leadership["report_date"].max())
    ]
    quadrant = latest.dropna(
        subset=["near_relative_growth_spread_pp", "far_relative_growth_spread_pp"]
    )

    assert set(quadrant["sector"]) == {"Energy", "Information Technology"}
    assert len(quadrant) == quadrant["sector"].nunique() == 2
