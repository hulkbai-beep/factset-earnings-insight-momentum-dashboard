"""Transparent, UI-independent dashboard metrics."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from typing import Final

import pandas as pd


FOUR_WEEK_DAYS: Final = 28
THIRTEEN_WEEK_DAYS: Final = 91
MAX_STALENESS_DAYS: Final = 14
GROWTH_METRICS: Final = ("earnings_growth_pct", "revenue_growth_pct")
SAFE_STATUSES: Final = frozenset({"SUCCESS", "SUCCESS_WITH_WARNINGS"})
PARTIAL_STATUSES: Final = frozenset({*SAFE_STATUSES, "PARTIAL"})


def _require_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def _timestamp(value: object) -> pd.Timestamp:
    result = pd.to_datetime(value, errors="raise")
    if isinstance(result, pd.DatetimeIndex):
        raise TypeError("Expected a scalar date")
    return pd.Timestamp(result).normalize()


def eps_revision_pct(current_eps: object, historical_eps: object) -> float | None:
    """Return the percentage EPS change, preserving missing/zero comparisons."""

    if pd.isna(current_eps) or pd.isna(historical_eps):
        return None
    current = float(current_eps)
    historical = float(historical_eps)
    if not math.isfinite(current) or not math.isfinite(historical) or historical == 0:
        return None
    return (current / historical - 1.0) * 100.0


def calculate_eps_momentum(
    bottom_up_eps: pd.DataFrame,
    *,
    max_staleness_days: int = MAX_STALENESS_DAYS,
) -> pd.DataFrame:
    """Add 1P, 4W, and 13W EPS changes for each exact period.

    Calendar-window matches use the most recent non-null observation for the
    exact period on or before the 28/91-day anchor and reject it when it is more
    than ``max_staleness_days`` before that anchor.
    """

    _require_columns(bottom_up_eps, ("report_date", "period", "eps"), "bottom_up_eps")
    if max_staleness_days < 0:
        raise ValueError("max_staleness_days must be non-negative")

    result = bottom_up_eps.copy()
    result["report_date"] = pd.to_datetime(result["report_date"], errors="raise").dt.normalize()
    if result.duplicated(["period", "report_date"]).any():
        raise ValueError("bottom_up_eps must contain at most one row per period/report_date")
    sort_columns = ["period", "report_date"]
    if "report_id" in result.columns:
        sort_columns.append("report_id")
    result = result.sort_values(sort_columns, kind="stable").reset_index(drop=True)

    eps_lookup = {
        (str(row.period), pd.Timestamp(row.report_date)): row.eps
        for row in result[["period", "report_date", "eps"]].itertuples(index=False)
    }
    valid_dates_by_period = {
        str(period): sorted(group.loc[group["eps"].notna(), "report_date"].tolist())
        for period, group in result.groupby("period", sort=False)
    }

    def previous_valid_match(current_date: pd.Timestamp, period: str) -> pd.Timestamp:
        eligible = [date for date in valid_dates_by_period.get(period, []) if date < current_date]
        return eligible[-1] if eligible else pd.NaT

    def calendar_match(
        current_date: pd.Timestamp,
        period: str,
        window_days: int,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        anchor = current_date - pd.Timedelta(days=window_days)
        eligible = [date for date in valid_dates_by_period.get(period, []) if date <= anchor]
        if not eligible:
            return anchor, pd.NaT
        comparison = pd.Timestamp(eligible[-1])
        if (anchor - comparison).days > max_staleness_days:
            return anchor, pd.NaT
        return anchor, comparison

    comparison_1p_dates: list[pd.Timestamp] = []
    comparison_4w_dates: list[pd.Timestamp] = []
    comparison_13w_dates: list[pd.Timestamp] = []
    anchor_4w_dates: list[pd.Timestamp] = []
    anchor_13w_dates: list[pd.Timestamp] = []
    changes_1p: list[float | None] = []
    changes_4w: list[float | None] = []
    changes_13w: list[float | None] = []

    for row in result[["report_date", "period", "eps"]].itertuples(index=False):
        current_date = pd.Timestamp(row.report_date)
        period = str(row.period)
        date_1p = previous_valid_match(current_date, period)
        anchor_4w, date_4w = calendar_match(current_date, period, FOUR_WEEK_DAYS)
        anchor_13w, date_13w = calendar_match(current_date, period, THIRTEEN_WEEK_DAYS)

        comparison_1p_dates.append(date_1p)
        comparison_4w_dates.append(date_4w)
        comparison_13w_dates.append(date_13w)
        anchor_4w_dates.append(anchor_4w)
        anchor_13w_dates.append(anchor_13w)
        changes_1p.append(
            eps_revision_pct(row.eps, eps_lookup.get((period, date_1p)))
            if not pd.isna(date_1p)
            else None
        )
        changes_4w.append(
            eps_revision_pct(row.eps, eps_lookup.get((period, date_4w)))
            if not pd.isna(date_4w)
            else None
        )
        changes_13w.append(
            eps_revision_pct(row.eps, eps_lookup.get((period, date_13w)))
            if not pd.isna(date_13w)
            else None
        )

    result["comparison_1p_date"] = comparison_1p_dates
    result["anchor_4w_date"] = anchor_4w_dates
    result["comparison_4w_date"] = comparison_4w_dates
    result["anchor_13w_date"] = anchor_13w_dates
    result["comparison_13w_date"] = comparison_13w_dates
    result["change_1p_pct"] = pd.array(changes_1p, dtype="Float64")
    result["change_4w_pct"] = pd.array(changes_4w, dtype="Float64")
    result["change_13w_pct"] = pd.array(changes_13w, dtype="Float64")
    return result


def select_relevant_eps_periods(
    bottom_up_eps: pd.DataFrame,
    index_metrics: pd.DataFrame | None = None,
    *,
    as_of_date: object | None = None,
    count: int = 2,
) -> tuple[str, ...]:
    """Select current/future calendar-year EPS periods without hardcoding years."""

    _require_columns(bottom_up_eps, ("report_date", "period"), "bottom_up_eps")
    if count < 1:
        raise ValueError("count must be at least one")
    eps = bottom_up_eps.copy()
    eps["report_date"] = pd.to_datetime(eps["report_date"], errors="raise").dt.normalize()
    cutoff = _timestamp(as_of_date) if as_of_date is not None else eps["report_date"].max()
    eligible = eps.loc[eps["report_date"] <= cutoff]
    if eligible.empty:
        return ()
    latest_date = eligible["report_date"].max()
    latest = eligible.loc[eligible["report_date"] == latest_date]
    if "period_type" in latest.columns:
        latest = latest.loc[latest["period_type"] == "calendar_year"]
    else:
        latest = latest.loc[latest["period"].astype(str).str.fullmatch(r"CY\d{4}")]
    available = set(latest["period"].dropna().astype(str))

    selected: list[str] = []
    if index_metrics is not None and not index_metrics.empty:
        _require_columns(
            index_metrics,
            ("report_date", "near_year_period", "far_year_period"),
            "index_metrics",
        )
        metrics = index_metrics.copy()
        metrics["report_date"] = pd.to_datetime(metrics["report_date"], errors="raise").dt.normalize()
        metrics = metrics.loc[metrics["report_date"] <= cutoff].sort_values("report_date")
        if not metrics.empty:
            current = metrics.iloc[-1]
            for column in ("near_year_period", "far_year_period"):
                value = current[column]
                if pd.notna(value) and str(value) in available and str(value) not in selected:
                    selected.append(str(value))

    if len(selected) < count:
        parsed = sorted(
            (
                (int(match.group(1)), period)
                for period in available
                if (match := re.fullmatch(r"CY(\d{4})", period))
            ),
            key=lambda item: item[0],
        )
        current_or_future = [period for year, period in parsed if year >= latest_date.year]
        fallback = current_or_future or [period for _, period in parsed[-count:]]
        for period in fallback:
            if period not in selected:
                selected.append(period)
            if len(selected) == count:
                break
    return tuple(selected[:count])


def default_valuation_multiples(
    index_metrics: pd.DataFrame,
    *,
    as_of_date: object | None = None,
) -> tuple[float, float, float] | None:
    """Return observed P/E references sorted into low/base/high defaults.

    The three inputs are the selected report's current forward 12-month P/E,
    five-year average, and ten-year average.  Returning ``None`` instead of a
    fallback keeps the scenario unavailable when any canonical reference is
    missing or invalid.
    """

    required = (
        "report_date",
        "forward_12m_pe",
        "forward_12m_pe_5y_avg",
        "forward_12m_pe_10y_avg",
    )
    _require_columns(index_metrics, required, "index_metrics")
    if index_metrics.empty:
        return None

    working = index_metrics.loc[:, required].copy()
    working["report_date"] = pd.to_datetime(
        working["report_date"], errors="raise"
    ).dt.normalize()
    cutoff = (
        _timestamp(as_of_date)
        if as_of_date is not None
        else working["report_date"].max()
    )
    current = working.loc[working["report_date"].eq(cutoff)]
    if current.empty:
        return None
    row = current.iloc[-1]
    values: list[float] = []
    for column in required[1:]:
        value = row[column]
        if pd.isna(value):
            return None
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0:
            return None
        values.append(numeric)
    low, base, high = sorted(values)
    return low, base, high


def calculate_valuation_scenarios(
    bottom_up_eps: pd.DataFrame,
    *,
    periods: Sequence[str],
    as_of_date: object,
    low_pe: float,
    base_pe: float,
    high_pe: float,
) -> pd.DataFrame:
    """Calculate transparent index-level scenarios as EPS × selected P/E.

    This is deterministic scenario analysis, not a statistical price forecast.
    It uses only exact-period EPS observations from the selected report date;
    missing observations remain missing and are never backfilled.
    """

    _require_columns(bottom_up_eps, ("report_date", "period", "eps"), "bottom_up_eps")
    multiples = (float(low_pe), float(base_pe), float(high_pe))
    if not all(math.isfinite(value) and value > 0 for value in multiples):
        raise ValueError("Scenario P/E multiples must be finite and greater than zero")
    if not low_pe <= base_pe <= high_pe:
        raise ValueError("Scenario P/E multiples must satisfy low <= base <= high")

    selected_periods = tuple(dict.fromkeys(str(period) for period in periods))
    columns = [
        "report_date",
        "period",
        "eps",
        "low_pe",
        "base_pe",
        "high_pe",
        "low_index_level",
        "base_index_level",
        "high_index_level",
    ]
    if not selected_periods:
        return pd.DataFrame(columns=columns)

    report_date = _timestamp(as_of_date)
    working = bottom_up_eps.loc[:, ["report_date", "period", "eps"]].copy()
    working["report_date"] = pd.to_datetime(
        working["report_date"], errors="raise"
    ).dt.normalize()
    current = working.loc[
        working["report_date"].eq(report_date)
        & working["period"].astype(str).isin(selected_periods)
    ]
    if current.duplicated("period").any():
        raise ValueError("bottom_up_eps must contain at most one row per period/report_date")
    eps_by_period = current.set_index(current["period"].astype(str))["eps"]

    records: list[dict[str, object]] = []
    for period in selected_periods:
        eps = eps_by_period.get(period, pd.NA)
        numeric_eps = None
        if pd.notna(eps):
            candidate = float(eps)
            numeric_eps = candidate if math.isfinite(candidate) else None
        records.append(
            {
                "report_date": report_date,
                "period": period,
                "eps": numeric_eps,
                "low_pe": multiples[0],
                "base_pe": multiples[1],
                "high_pe": multiples[2],
                "low_index_level": numeric_eps * multiples[0] if numeric_eps is not None else None,
                "base_index_level": numeric_eps * multiples[1] if numeric_eps is not None else None,
                "high_index_level": numeric_eps * multiples[2] if numeric_eps is not None else None,
            }
        )
    result = pd.DataFrame.from_records(records, columns=columns)
    for column in (
        "eps",
        "low_pe",
        "base_pe",
        "high_pe",
        "low_index_level",
        "base_index_level",
        "high_index_level",
    ):
        result[column] = pd.array(result[column], dtype="Float64")
    return result


def calculate_sector_index_spreads(
    sector_growth: pd.DataFrame,
    index_growth: pd.DataFrame,
    *,
    metrics: str | Sequence[str] = GROWTH_METRICS,
) -> pd.DataFrame:
    """Match sector/index rows on report and period, then subtract in pp."""

    requested = (metrics,) if isinstance(metrics, str) else tuple(metrics)
    invalid = sorted(set(requested) - set(GROWTH_METRICS))
    if invalid:
        raise ValueError("Unsupported growth metrics: " + ", ".join(invalid))
    _require_columns(sector_growth, ("period", *requested), "sector_growth")
    _require_columns(index_growth, ("period", *requested), "index_growth")

    if "report_id" in sector_growth.columns and "report_id" in index_growth.columns:
        keys = ["report_id", "period"]
    elif "report_date" in sector_growth.columns and "report_date" in index_growth.columns:
        keys = ["report_date", "period"]
    else:
        raise ValueError("Both inputs must share report_id or report_date")
    for optional in ("report_date", "period_type", "estimate_status"):
        if optional not in keys and optional in sector_growth.columns and optional in index_growth.columns:
            keys.append(optional)

    baseline = index_growth.loc[:, [*keys, *requested]].copy()
    if baseline.duplicated(keys).any():
        raise ValueError("index_growth must contain one baseline row per matched report/period")
    baseline = baseline.rename(columns={metric: f"index_{metric}" for metric in requested})
    result = sector_growth.merge(baseline, how="left", on=keys, validate="many_to_one")
    for metric in requested:
        stem = metric.removesuffix("_growth_pct")
        result[f"{stem}_growth_spread_pp"] = (
            pd.to_numeric(result[metric], errors="coerce")
            - pd.to_numeric(result[f"index_{metric}"], errors="coerce")
        ).astype("Float64")
    return result


def detect_horizon_rolls(leadership: pd.DataFrame) -> pd.DataFrame:
    """Return one near/far horizon record and roll flag per report date."""

    _require_columns(
        leadership,
        ("report_date", "near_year_period", "far_year_period"),
        "leadership",
    )
    columns = ["report_date", "near_year_period", "far_year_period"]
    horizons = leadership.loc[:, columns].copy()
    horizons["report_date"] = pd.to_datetime(horizons["report_date"], errors="raise").dt.normalize()
    if horizons.groupby("report_date", dropna=False)[columns[1:]].nunique(dropna=False).max().max() > 1:
        raise ValueError("leadership contains multiple horizon pairs for one report date")
    horizons = horizons.drop_duplicates().sort_values("report_date").reset_index(drop=True)
    derived = (
        horizons[["near_year_period", "far_year_period"]]
        .ne(horizons[["near_year_period", "far_year_period"]].shift())
        .any(axis=1)
    )
    if not derived.empty:
        derived.iloc[0] = False

    if "horizon_roll_flag" in leadership.columns:
        supplied = leadership.copy()
        supplied["report_date"] = pd.to_datetime(supplied["report_date"], errors="raise").dt.normalize()
        supplied_flags = supplied.groupby("report_date")["horizon_roll_flag"].max()
        horizons["horizon_roll_flag"] = horizons["report_date"].map(supplied_flags).fillna(False).astype(bool) | derived
    else:
        horizons["horizon_roll_flag"] = derived
    horizons["horizon_regime_id"] = horizons["horizon_roll_flag"].astype(int).cumsum()
    return horizons


def horizon_roll_dates(leadership: pd.DataFrame) -> tuple[pd.Timestamp, ...]:
    horizons = detect_horizon_rolls(leadership)
    return tuple(horizons.loc[horizons["horizon_roll_flag"], "report_date"])


def assign_horizon_regimes(leadership: pd.DataFrame) -> pd.DataFrame:
    """Attach a regime id suitable for splitting chart lines at horizon rolls."""

    horizons = detect_horizon_rolls(leadership)
    result = leadership.copy()
    result["report_date"] = pd.to_datetime(result["report_date"], errors="raise").dt.normalize()
    result = result.drop(columns=["horizon_roll_flag", "horizon_regime_id"], errors="ignore")
    return result.merge(horizons, how="left", on=["report_date", "near_year_period", "far_year_period"])


def split_at_horizon_rolls(leadership: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    """Split leadership history so a chart cannot connect across horizon regimes."""

    assigned = assign_horizon_regimes(leadership)
    return tuple(
        group.copy()
        for _, group in assigned.groupby("horizon_regime_id", sort=True, dropna=False)
    )


def add_guidance_metrics(guidance: pd.DataFrame) -> pd.DataFrame:
    """Add completeness and balance fields without converting NULL to zero."""

    _require_columns(
        guidance,
        ("positive_count", "negative_count", "positive_pct", "negative_pct"),
        "guidance",
    )
    result = guidance.copy()
    positive_count = pd.to_numeric(result["positive_count"], errors="coerce")
    negative_count = pd.to_numeric(result["negative_count"], errors="coerce")
    positive_pct = pd.to_numeric(result["positive_pct"], errors="coerce")
    negative_pct = pd.to_numeric(result["negative_pct"], errors="coerce")

    result["guidance_counts_complete"] = positive_count.notna() & negative_count.notna()
    result["guidance_percentages_complete"] = positive_pct.notna() & negative_pct.notna()
    total = (positive_count + negative_count).where(result["guidance_counts_complete"])
    result["guidance_total_count"] = pd.array(total, dtype="Float64")
    result["guidance_count_balance"] = pd.array(
        (positive_count - negative_count).where(result["guidance_counts_complete"]),
        dtype="Float64",
    )

    published_balance = (positive_pct - negative_pct).where(
        result["guidance_percentages_complete"]
    )
    derived_balance = ((positive_count - negative_count) / total * 100.0).where(total > 0)
    balance = published_balance.combine_first(derived_balance)
    result["guidance_balance_pct"] = pd.array(balance, dtype="Float64")
    result["guidance_balance_source"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result.loc[result["guidance_percentages_complete"], "guidance_balance_source"] = "PUBLISHED_PERCENTAGES"
    derived_mask = result["guidance_balance_source"].isna() & result["guidance_counts_complete"] & total.gt(0)
    result.loc[derived_mask, "guidance_balance_source"] = "DERIVED_FROM_COUNTS"
    return result


def guidance_completeness(guidance: pd.DataFrame) -> pd.DataFrame:
    """Return row-level guidance completeness flags."""

    enriched = add_guidance_metrics(guidance)
    return enriched.loc[:, ["guidance_counts_complete", "guidance_percentages_complete"]]


def guidance_balance(guidance: pd.DataFrame) -> pd.Series:
    """Return nullable positive-minus-negative guidance balance in pp."""

    return add_guidance_metrics(guidance)["guidance_balance_pct"]


def latest_safe_report(
    reports: pd.DataFrame,
    *,
    include_partial: bool = False,
) -> pd.Series | None:
    """Return the latest report allowed by the dashboard safety policy."""

    _require_columns(reports, ("report_date",), "reports")
    allowed_statuses = PARTIAL_STATUSES if include_partial else SAFE_STATUSES
    if "status" in reports.columns:
        mask = reports["status"].isin(allowed_statuses)
    elif "phase3_report_safe" in reports.columns and not include_partial:
        mask = pd.to_numeric(reports["phase3_report_safe"], errors="coerce").eq(1)
    elif include_partial:
        raise ValueError("reports must include status when include_partial=True")
    else:
        mask = pd.Series(True, index=reports.index)

    eligible = reports.loc[mask].copy()
    if eligible.empty:
        return None
    eligible["report_date"] = pd.to_datetime(eligible["report_date"], errors="raise").dt.normalize()
    sort_columns = ["report_date"] + (["report_id"] if "report_id" in eligible.columns else [])
    return eligible.sort_values(sort_columns, kind="stable").iloc[-1].copy()
