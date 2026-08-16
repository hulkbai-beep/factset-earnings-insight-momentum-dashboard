"""Sector profitability and valuation page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, models, ui
from factset_dashboard.filters import DashboardContext, at_report_date


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Profitability meets price",
        "Sector Quality & Valuation",
        "Rank margin expansion and valuation, then compare forward relative growth with each sector's own historical P/E context.",
    )
    margin_history = bundle["sector_margin"]
    valuation_history = bundle["sector_valuation"]
    margin = at_report_date(margin_history, context.selected_report_date)
    valuation = at_report_date(valuation_history, context.selected_report_date)

    ranking_options = {
        "Premium / discount to 5Y average": ("premium_to_5y_pct", "Premium / discount to 5Y average (%)"),
        "Premium / discount to 10Y average": ("premium_to_10y_pct", "Premium / discount to 10Y average (%)"),
        "Forward 12M P/E": ("forward_12m_pe", "Forward 12M P/E (×)"),
    }
    ranking_label = st.selectbox("Sector valuation ranking", list(ranking_options), key="valuation_ranking")
    ranking_field, ranking_axis = ranking_options[ranking_label]

    left, right = st.columns(2)
    with left:
        st.subheader("Margin expansion ranking")
        st.plotly_chart(
            charts.horizontal_bar(
                margin,
                x="margin_yoy_change_pp",
                y="sector",
                x_title="YoY margin change (pp)",
                color="margin_yoy_change_pp",
                hover_data=["current_net_profit_margin_pct", "year_ago_net_profit_margin_pct"],
            ),
            width="stretch",
        )
    with right:
        st.subheader(ranking_label)
        st.plotly_chart(
            charts.horizontal_bar(
                valuation,
                x=ranking_field,
                y="sector",
                x_title=ranking_axis,
                color=ranking_field,
                hover_data=["forward_12m_pe", "five_year_avg_forward_pe", "premium_to_10y_pct"],
            ),
            width="stretch",
        )

    all_sectors = sorted(margin_history["sector"].dropna().unique())
    selected_sector = st.selectbox(
        "Sector margin history",
        all_sectors,
        index=all_sectors.index("Information Technology") if "Information Technology" in all_sectors else 0,
        key="quality_sector",
    )
    sector_margin = margin_history.loc[margin_history["sector"].eq(selected_sector)].sort_values("report_date")
    margin_fig = charts.line_chart(
        sector_margin,
        x="report_date",
        series=[
            ("current_net_profit_margin_pct", "Current margin"),
            ("year_ago_net_profit_margin_pct", "Year-ago margin"),
        ],
        y_title="Net profit margin (%)",
        hover_suffix="%",
    )
    st.plotly_chart(margin_fig, width="stretch")
    st.caption("Sector five-year margin averages are unavailable in the current database and are intentionally not charted.")

    st.subheader("Growth vs valuation opportunity map")
    opportunity = models.growth_valuation_opportunity(
        bundle["sector_leadership"],
        valuation_history,
        context.selected_report_date,
    )
    st.plotly_chart(charts.opportunity_map(opportunity), width="stretch")
    ui.note(
        "These quadrants describe combinations of relative growth and historical valuation. They are research regimes, not automated investment recommendations.",
        quality=True,
    )

    with st.expander("Sector valuation detail"):
        columns = [
            "sector",
            "forward_12m_pe",
            "five_year_avg_forward_pe",
            "ten_year_avg_forward_pe",
            "premium_to_5y_pct",
            "premium_to_10y_pct",
        ]
        table = valuation.reindex(columns=columns).rename(
            columns={
                "sector": "Sector",
                "forward_12m_pe": "Forward P/E",
                "five_year_avg_forward_pe": "5Y average P/E",
                "ten_year_avg_forward_pe": "10Y average P/E",
                "premium_to_5y_pct": "Premium to 5Y",
                "premium_to_10y_pct": "Premium to 10Y",
            }
        )
        st.dataframe(
            ui.dataframe_for_display(
                table,
                {
                    "Forward P/E": "pe",
                    "5Y average P/E": "pe",
                    "10Y average P/E": "pe",
                    "Premium to 5Y": "pct",
                    "Premium to 10Y": "pct",
                },
            ),
            hide_index=True,
            width="stretch",
        )
