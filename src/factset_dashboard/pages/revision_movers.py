"""Top company EPS revision movers page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, ui
from factset_dashboard.filters import DashboardContext, at_report_date


def _mover_panel(frame: pd.DataFrame, direction: str) -> None:
    title = "Largest upward revisions" if direction == "UP" else "Largest downward revisions"
    st.subheader(title)
    selected = frame.loc[frame["direction"].eq(direction)].sort_values("rank")
    st.plotly_chart(
        charts.horizontal_bar(
            selected,
            x="revision_pct",
            y="company",
            x_title="EPS revision (%)",
            color="revision_pct",
            height=420,
            hover_data=["rank", "period", "revision_window"],
        ),
        width="stretch",
    )
    table = selected[
        ["rank", "company", "revision_pct", "period", "revision_window", "chart_scope"]
    ].rename(
        columns={
            "rank": "Rank",
            "company": "Company",
            "revision_pct": "Revision",
            "period": "Period",
            "revision_window": "Revision window",
            "chart_scope": "Scope",
        }
    )
    st.dataframe(ui.dataframe_for_display(table, {"Revision": "pct"}), hide_index=True, width="stretch")


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Idea generation",
        "Top S&P 500 EPS Revision Movers",
        "Inspect FactSet's largest company-level upward and downward EPS revisions for anomaly discovery.",
    )
    ui.note(
        "This source is a Top-10 movers extract. It is not S&P 500 revision breadth and is not the dashboard's primary market-momentum signal.",
        quality=True,
    )
    current = at_report_date(bundle["eps_revisions"], context.selected_report_date)
    periods = sorted(current["period"].dropna().unique())
    if not periods:
        ui.note("No revision-mover observations are available for this report date.", quality=True)
        return
    period = st.selectbox("Revision period", periods, key="revision_period")
    current = current.loc[current["period"].eq(period)].copy()
    metadata = current.iloc[0]
    st.caption(
        f"Period: {period} · Window: {metadata.get('revision_window', 'N/A')} · Scope: {metadata.get('chart_scope', 'N/A')}"
    )
    left, right = st.columns(2)
    with left:
        _mover_panel(current, "UP")
    with right:
        _mover_panel(current, "DOWN")
