"""Sector Leadership page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, metrics, ui
from factset_dashboard.filters import DashboardContext, at_report_date


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Sector fundamentals",
        "Sector Leadership",
        "Compare each sector's earnings growth with the S&P 500 across the current and farther calendar-year horizons.",
    )
    history = bundle["sector_leadership"]
    current = at_report_date(history, context.selected_report_date)
    if current.empty:
        ui.note(
            f"Leadership observations are unavailable for {context.selected_date_string}. The gap is preserved; choose another report date.",
            quality=True,
        )
    elif current["horizon_roll_flag"].fillna(0).astype(int).eq(1).any():
        near = current["near_year_period"].dropna().iloc[0] if current["near_year_period"].notna().any() else "N/A"
        far = current["far_year_period"].dropna().iloc[0] if current["far_year_period"].notna().any() else "N/A"
        ui.note(
            f"Forecast horizon roll: this report begins the {near} / {far} regime. Classification changes across this boundary are not ordinary publication-to-publication transitions."
        )

    st.subheader("Sector leadership quadrant")
    st.plotly_chart(charts.leadership_quadrant(current), width="stretch")
    ui.note(
        "Quadrants are analytical regimes based on relative earnings growth—not buy, sell, or allocation recommendations.",
        quality=True,
    )

    st.subheader("Leadership table")
    sort_options = {
        "Far-year relative growth": "far_relative_growth_spread_pp",
        "Relative growth transition": "relative_growth_transition_pp",
        "Classification": "classification",
    }
    sort_label = st.selectbox("Sort table by", list(sort_options), key="leadership_sort")
    table_columns = [
        "sector",
        "near_year_period",
        "far_year_period",
        "near_relative_growth_spread_pp",
        "far_relative_growth_spread_pp",
        "relative_growth_transition_pp",
        "classification",
        "data_quality",
    ]
    table = current.reindex(columns=table_columns).sort_values(
        sort_options[sort_label], ascending=False, na_position="last"
    )
    table = table.rename(
        columns={
            "sector": "Sector",
            "near_year_period": "Near-year period",
            "far_year_period": "Far-year period",
            "near_relative_growth_spread_pp": "Near spread",
            "far_relative_growth_spread_pp": "Far spread",
            "relative_growth_transition_pp": "Transition",
            "classification": "Classification",
            "data_quality": "Data quality",
        }
    )
    st.dataframe(
        ui.dataframe_for_display(table, {"Near spread": "pp", "Far spread": "pp", "Transition": "pp"}),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Leadership history")
    roll_dates = metrics.horizon_roll_dates(history)
    st.plotly_chart(
        charts.leadership_heatmap(history, roll_dates, report_dates=bundle["reports"]["report_date"]),
        width="stretch",
    )
    st.caption("Blank cells are missing observations. Gold markers identify forecast-horizon changes.")
