"""Secondary analyst target and rating context."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, ui
from factset_dashboard.filters import DashboardContext, at_report_date


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Secondary context",
        "Analyst Sentiment",
        "Review bottom-up target prices, implied upside, and recommendation mix after the dashboard's earnings-fundamental evidence.",
    )
    ui.note(
        "Analyst targets are deliberately lower priority than revisions, growth, margin, valuation, guidance, and earnings quality.",
        quality=True,
    )
    target = at_report_date(bundle["target_prices"], context.selected_report_date)
    row = target.iloc[-1] if not target.empty else pd.Series(dtype=object)
    cards = st.columns(5)
    values = [
        ("Bottom-up target", row.get("bottom_up_target_price"), "price"),
        ("Implied upside", row.get("implied_upside_pct"), "pct"),
        ("Buy ratings", row.get("buy_rating_pct"), "pct"),
        ("Hold ratings", row.get("hold_rating_pct"), "pct"),
        ("Sell ratings", row.get("sell_rating_pct"), "pct"),
    ]
    for column, (label, value, kind) in zip(cards, values):
        with column:
            ui.metric_card(label, value, kind=kind)

    st.subheader("Sector implied target upside")
    sectors = at_report_date(bundle["sector_target_prices"], context.selected_report_date)
    st.plotly_chart(
        charts.horizontal_bar(
            sectors,
            x="implied_upside_pct",
            y="sector",
            x_title="Implied target upside (%)",
            color="implied_upside_pct",
            height=500,
        ),
        width="stretch",
    )
    st.caption("An absent sector target is shown as unavailable, never as zero upside.")

    st.subheader("S&P 500 target history")
    history = bundle["target_prices"].sort_values("report_date")
    st.plotly_chart(
        charts.line_chart(
            history,
            x="report_date",
            series=[("implied_upside_pct", "Implied upside")],
            y_title="Implied upside (%)",
            hover_suffix="%",
        ),
        width="stretch",
    )
