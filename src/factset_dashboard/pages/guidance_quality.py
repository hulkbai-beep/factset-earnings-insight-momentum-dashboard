"""Guidance and earnings confirmation page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, metrics, ui
from factset_dashboard.filters import DashboardContext, at_report_date


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Confirmation indicators",
        "Guidance & Earnings Quality",
        "Assess whether management guidance and reported beats confirm—or contradict—the forward earnings picture.",
    )
    guidance = metrics.add_guidance_metrics(bundle["guidance"])
    index = guidance.loc[guidance["scope"].eq("INDEX")].copy()
    periods = sorted(index["period"].dropna().unique())
    if periods:
        preferred = index.loc[
            index["period_type"].eq("fiscal_year_range")
            & index["report_date"].le(context.selected_report_date)
        ].sort_values("report_date")
        preferred_period = preferred.iloc[-1]["period"] if not preferred.empty else periods[-1]
        default_index = periods.index(preferred_period)
        period = st.selectbox("Index guidance period", periods, index=default_index, key="guidance_index_period")
        trend = index.loc[index["period"].eq(period)].sort_values("report_date")
    else:
        period = "N/A"
        trend = index
    st.subheader("Index guidance trend")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            charts.line_chart(
                trend,
                x="report_date",
                series=[("positive_count", "Positive guidance"), ("negative_count", "Negative guidance")],
                y_title="Company count",
            ),
            width="stretch",
        )
    with right:
        percent_series = [
            ("positive_pct", "Positive guidance"),
            ("negative_pct", "Negative guidance"),
            ("historical_5y_negative_guidance_avg_pct", "5Y negative average"),
            ("historical_10y_negative_guidance_avg_pct", "10Y negative average"),
        ]
        st.plotly_chart(
            charts.line_chart(trend, x="report_date", series=percent_series, y_title="Guidance share (%)", hover_suffix="%"),
            width="stretch",
        )
    st.caption(f"Period shown: {period}. Historical averages appear only where FactSet published them.")

    st.subheader("Sector guidance")
    sector = at_report_date(guidance.loc[guidance["scope"].eq("SECTOR")], context.selected_report_date)
    sector_periods = sorted(sector["period"].dropna().unique())
    if sector_periods:
        sector_period = st.selectbox("Sector guidance period", sector_periods, key="guidance_sector_period")
        sector = sector.loc[sector["period"].eq(sector_period)].copy()
    complete = sector.loc[
        sector["guidance_counts_complete"] & sector["guidance_balance_pct"].notna()
    ].copy()
    usable, total = len(complete), len(sector)
    ui.note(
        f"{usable} of {total} sector observations have sufficient positive/negative information for a balance calculation. Incomplete rows remain N/A.",
        quality=True,
    )
    st.plotly_chart(
        charts.horizontal_bar(
            complete,
            x="guidance_balance_pct",
            y="sector",
            x_title="Positive minus negative guidance (pp)",
            color="guidance_balance_pct",
            hover_data=["positive_count", "negative_count", "guidance_balance_source"],
        ),
        width="stretch",
    )
    if not sector.empty:
        table = sector[
            [
                "sector",
                "period",
                "positive_count",
                "negative_count",
                "positive_pct",
                "negative_pct",
                "guidance_counts_complete",
                "guidance_percentages_complete",
            ]
        ].rename(
            columns={
                "sector": "Sector",
                "period": "Period",
                "positive_count": "Positive count",
                "negative_count": "Negative count",
                "positive_pct": "Positive %",
                "negative_pct": "Negative %",
                "guidance_counts_complete": "Counts complete",
                "guidance_percentages_complete": "Percentages complete",
            }
        )
        st.dataframe(
            ui.dataframe_for_display(table, {"Positive count": "count", "Negative count": "count", "Positive %": "pct", "Negative %": "pct"}),
            hide_index=True,
            width="stretch",
        )

    st.subheader("Earnings surprise confirmation")
    surprises = bundle["surprises"].sort_values("report_date")
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            charts.line_chart(
                surprises,
                x="report_date",
                series=[
                    ("positive_eps_surprise_pct", "Positive EPS surprises"),
                    ("positive_revenue_surprise_pct", "Positive revenue surprises"),
                ],
                y_title="Companies with positive surprise (%)",
                hover_suffix="%",
            ),
            width="stretch",
        )
    with right:
        st.plotly_chart(
            charts.line_chart(
                surprises,
                x="report_date",
                series=[
                    ("eps_surprise_magnitude_pct", "EPS surprise magnitude"),
                    ("revenue_surprise_magnitude_pct", "Revenue surprise magnitude"),
                ],
                y_title="Aggregate surprise magnitude (%)",
                hover_suffix="%",
            ),
            width="stretch",
        )
    st.caption("Surprises are confirmation indicators; missing earnings-season observations are not interpolated.")
