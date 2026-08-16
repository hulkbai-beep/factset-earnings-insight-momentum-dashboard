"""Sector earnings and revenue trend page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, metrics, models, ui
from factset_dashboard.filters import DashboardContext


def _period_sort_key(period: str) -> tuple[int, int, int]:
    text = str(period)
    if text.startswith("CY") and text[2:].isdigit():
        return (2, int(text[2:]), 0)
    if text.startswith("Q") and len(text.split()) == 2:
        quarter, year = text.split()
        if quarter[1:].isdigit() and year.isdigit():
            return (1, int(year), int(quarter[1:]))
    return (0, 0, 0)


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Like-for-like comparisons",
        "Sector Trends",
        "Track sector earnings and revenue growth against the S&P 500 for the exact same report and forecast period.",
    )
    sector_growth = bundle["sector_growth"]
    index_growth = bundle["period_growth"]
    sectors = sorted(sector_growth["sector"].dropna().unique())
    default_sectors = [value for value in ("Information Technology", "Financials") if value in sectors]
    selected_sectors = st.multiselect(
        "Sectors",
        sectors,
        default=default_sectors or sectors[:1],
        key="trend_sectors",
    )
    period_type = st.radio(
        "Forecast period type",
        options=["calendar_year", "quarter"],
        format_func=lambda value: "Calendar year" if value == "calendar_year" else "Quarter",
        index=0,
        horizontal=True,
        key="trend_period_type",
    )
    available_periods = sorted(
        sector_growth.loc[sector_growth["period_type"].eq(period_type), "period"].dropna().unique(),
        key=_period_sort_key,
        reverse=True,
    )
    if not selected_sectors or not available_periods:
        ui.note("Choose at least one sector and an available forecast period.", quality=True)
        return
    period = st.selectbox("Forecast period", available_periods, key="trend_period")
    st.caption("Estimate status remains in hover details because a move may combine estimate revisions and reported actuals.")

    st.subheader("Earnings growth: sectors vs S&P 500")
    earnings = models.sector_growth_comparison(
        sector_growth,
        index_growth,
        sectors=selected_sectors,
        period=period,
        metric="earnings",
        report_dates=bundle["reports"]["report_date"],
    )
    st.plotly_chart(charts.entity_growth_chart(earnings, y_title="Earnings growth (%)"), width="stretch")

    st.subheader("Revenue growth: sectors vs S&P 500")
    revenue = models.sector_growth_comparison(
        sector_growth,
        index_growth,
        sectors=selected_sectors,
        period=period,
        metric="revenue",
        report_dates=bundle["reports"]["report_date"],
    )
    st.plotly_chart(charts.entity_growth_chart(revenue, y_title="Revenue growth (%)"), width="stretch")

    st.subheader("Growth spread")
    spread_metric = st.radio(
        "Spread metric",
        ["earnings", "revenue"],
        horizontal=True,
        format_func=str.title,
        key="trend_spread_metric",
    )
    metric_column = f"{spread_metric}_growth_pct"
    spread_column = f"{spread_metric}_growth_spread_pp"
    spreads = metrics.calculate_sector_index_spreads(
        sector_growth,
        index_growth,
        metrics=metric_column,
    )
    spreads = models.sector_spread_history(
        spreads,
        sectors=selected_sectors,
        period=period,
        report_dates=bundle["reports"]["report_date"],
    )
    st.plotly_chart(charts.spread_chart(spreads, value_column=spread_column), width="stretch")
    st.caption("Above zero means sector growth exceeds the index; below zero means it trails. Missing inputs remain missing.")

    anomalies = models.detected_growth_provenance_anomalies(
        bundle["index_metrics"], bundle["observation_provenance"]
    )
    if not anomalies.empty:
        dates = ", ".join(sorted(pd.to_datetime(anomalies["report_date"]).dt.strftime("%Y-%m-%d").unique()))
        ui.note(
            f"Data-quality alert: the canonical S&P 500 earnings-growth baseline conflicts with linked source prose on {dates}. Both the index line and earnings-spread values preserve the canonical database value; review provenance before interpretation."
        )
