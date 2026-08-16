"""Chart-ready data models assembled from canonical query results.

This module intentionally contains joins and reshaping, keeping those operations
out of Streamlit page components and keeping chart builders presentation-only.
"""

from __future__ import annotations

import re

import pandas as pd


def eps_trend(eps: pd.DataFrame, periods: list[str]) -> pd.DataFrame:
    if eps.empty or not periods:
        return pd.DataFrame(columns=["report_date", *periods])
    scoped = eps.loc[(eps["period_type"] == "calendar_year") & eps["period"].isin(periods)].copy()
    if scoped.empty:
        return pd.DataFrame(columns=["report_date", *periods])
    return (
        scoped.pivot_table(index="report_date", columns="period", values="eps", aggfunc="last", dropna=False)
        .reindex(columns=periods)
        .reset_index()
        .sort_values("report_date")
    )


def growth_valuation_opportunity(
    leadership: pd.DataFrame,
    valuation: pd.DataFrame,
    report_date: pd.Timestamp | str,
) -> pd.DataFrame:
    """Match leadership and valuation by report ID and sector—never by proximity."""

    target = pd.Timestamp(report_date).normalize()
    leaders = leadership.loc[pd.to_datetime(leadership["report_date"]).dt.normalize().eq(target)].copy()
    values = valuation.loc[pd.to_datetime(valuation["report_date"]).dt.normalize().eq(target)].copy()
    leader_columns = [
        "report_id",
        "sector",
        "far_year_period",
        "far_relative_growth_spread_pp",
        "classification",
        "data_quality",
    ]
    value_columns = [
        "report_id",
        "sector",
        "forward_12m_pe",
        "premium_to_5y_pct",
        "premium_to_10y_pct",
    ]
    if leaders.empty or values.empty:
        return pd.DataFrame(columns=leader_columns + value_columns[2:])
    return leaders[leader_columns].merge(values[value_columns], on=["report_id", "sector"], how="inner")


def sector_growth_comparison(
    sector_growth: pd.DataFrame,
    index_growth: pd.DataFrame,
    *,
    sectors: list[str],
    period: str,
    metric: str,
    report_dates: list[pd.Timestamp] | pd.Series | None = None,
) -> pd.DataFrame:
    value_column = f"{metric}_growth_pct"
    sector_columns = [
        "report_id",
        "report_date",
        "period",
        "period_type",
        "estimate_status",
        "sector",
        value_column,
    ]
    index_columns = ["report_id", "report_date", "period", "period_type", "estimate_status", value_column]
    sector = sector_growth.loc[
        sector_growth["sector"].isin(sectors) & sector_growth["period"].eq(period), sector_columns
    ].copy()
    sector = sector.rename(columns={"sector": "entity", value_column: "growth_pct"})
    index = index_growth.loc[index_growth["period"].eq(period), index_columns].copy()
    index["entity"] = "S&P 500"
    index = index.rename(columns={value_column: "growth_pct"})
    combined = pd.concat([index, sector], ignore_index=True, sort=False)
    if report_dates is not None:
        dates = sorted({pd.Timestamp(value).normalize() for value in report_dates})
        entities = ["S&P 500", *sectors]
        spine = pd.MultiIndex.from_product(
            [dates, entities], names=["report_date", "entity"]
        ).to_frame(index=False)
        combined = spine.merge(combined, on=["report_date", "entity"], how="left", validate="one_to_one")
        combined["period"] = combined["period"].fillna(period)
    return combined.sort_values(["report_date", "entity"])


def sector_spread_history(
    spreads: pd.DataFrame,
    *,
    sectors: list[str],
    period: str,
    report_dates: list[pd.Timestamp] | pd.Series,
) -> pd.DataFrame:
    """Reindex sector spread observations to the report-date spine."""

    dates = sorted({pd.Timestamp(value).normalize() for value in report_dates})
    spine = pd.MultiIndex.from_product(
        [dates, sectors], names=["report_date", "sector"]
    ).to_frame(index=False)
    scoped = spreads.loc[spreads["sector"].isin(sectors) & spreads["period"].eq(period)].copy()
    result = spine.merge(scoped, on=["report_date", "sector"], how="left", validate="one_to_one")
    result["period"] = result["period"].fillna(period)
    return result.sort_values(["report_date", "sector"])


def guidance_quality_frame(guidance: pd.DataFrame) -> pd.DataFrame:
    result = guidance.copy()
    paired = result["positive_count"].notna() & result["negative_count"].notna()
    denominator = result["positive_count"] + result["negative_count"]
    result["counts_complete"] = paired
    result["derived_positive_share_pct"] = pd.NA
    valid = paired & denominator.gt(0)
    result.loc[valid, "derived_positive_share_pct"] = (
        result.loc[valid, "positive_count"] / denominator.loc[valid] * 100
    )
    return result


def warning_summary(warnings: pd.DataFrame) -> pd.DataFrame:
    if warnings.empty:
        return pd.DataFrame(columns=["report_date", "code", "severity", "warning_count"])
    return (
        warnings.groupby(["report_date", "code", "severity"], dropna=False)
        .size()
        .rename("warning_count")
        .reset_index()
        .sort_values(["report_date", "warning_count"], ascending=[False, False])
    )


def valuation_premiums(snapshot: pd.Series) -> dict[str, float | None]:
    current = pd.to_numeric(pd.Series([snapshot.get("forward_12m_pe")]), errors="coerce").iloc[0]
    result: dict[str, float | None] = {}
    for label, field in (("premium_to_5y_pct", "forward_12m_pe_5y_avg"), ("premium_to_10y_pct", "forward_12m_pe_10y_avg")):
        baseline = pd.to_numeric(pd.Series([snapshot.get(field)]), errors="coerce").iloc[0]
        result[label] = None if pd.isna(current) or pd.isna(baseline) or baseline == 0 else (current / baseline - 1) * 100
    return result


def detected_growth_provenance_anomalies(
    index_metrics: pd.DataFrame,
    provenance: pd.DataFrame,
) -> pd.DataFrame:
    """Detect canonical near-year growth values contradicted by numeric source prose.

    This intentionally reports candidates for review; it never substitutes the
    provenance value into the canonical series.
    """

    if index_metrics.empty or provenance.empty:
        return pd.DataFrame(columns=["report_date", "canonical_value", "raw_text"])
    evidence = provenance.loc[
        provenance["table_name"].eq("index_metrics")
        & provenance["field_name"].eq("current_calendar_year_earnings_growth_pct")
        & provenance["raw_text"].notna(),
        ["report_id", "report_date", "raw_text", "source_page"],
    ].copy()
    narrative_pattern = re.compile(r"earnings growth of\s+(-?\d+(?:\.\d+)?)%", re.IGNORECASE)
    evidence["narrative_value"] = evidence["raw_text"].map(
        lambda text: float(match.group(1)) if (match := narrative_pattern.search(str(text))) else pd.NA
    )
    evidence = evidence.loc[evidence["narrative_value"].notna()]
    canonical = index_metrics[["report_id", "report_date", "near_year_earnings_growth_pct"]].rename(
        columns={"near_year_earnings_growth_pct": "canonical_value"}
    )
    candidates = canonical.merge(evidence, on=["report_id", "report_date"], how="inner")
    candidates["possible_conflict"] = (
        pd.to_numeric(candidates["canonical_value"], errors="coerce")
        - pd.to_numeric(candidates["narrative_value"], errors="coerce")
    ).abs().gt(0.05)
    return candidates.loc[candidates["possible_conflict"]].drop(columns=["possible_conflict"])


def market_horizon_regimes(
    index_metrics: pd.DataFrame,
    roll_dates: list[pd.Timestamp] | tuple[pd.Timestamp, ...],
) -> pd.DataFrame:
    """Assign each market snapshot to a forecast-horizon regime by date."""

    result = index_metrics.copy()
    result["report_date"] = pd.to_datetime(result["report_date"], errors="coerce").dt.normalize()
    normalized_rolls = sorted(pd.Timestamp(value).normalize() for value in roll_dates)
    result["horizon_regime_id"] = result["report_date"].map(
        lambda current: sum(current >= roll for roll in normalized_rolls) if pd.notna(current) else pd.NA
    )
    return result
