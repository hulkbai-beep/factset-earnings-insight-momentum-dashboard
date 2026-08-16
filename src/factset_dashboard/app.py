"""Application shell and persistent global filters."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import streamlit as st

from factset_dashboard import db, queries, ui
from factset_dashboard.filters import DashboardContext, date_options, subset_bundle
from factset_dashboard.pages import (
    render_analyst_sentiment,
    render_data_quality,
    render_guidance_quality,
    render_market_regime,
    render_revision_movers,
    render_sector_leadership,
    render_sector_quality,
    render_sector_trends,
)


PAGES = {
    "Market Regime": render_market_regime,
    "Sector Leadership": render_sector_leadership,
    "Sector Trends": render_sector_trends,
    "Sector Quality & Valuation": render_sector_quality,
    "Guidance & Earnings Quality": render_guidance_quality,
    "Revision Movers": render_revision_movers,
    "Analyst Sentiment": render_analyst_sentiment,
    "Data Quality & Provenance": render_data_quality,
}


def _command_line_database() -> Path | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db-path", type=Path)
    args, _ = parser.parse_known_args()
    return args.db_path.resolve() if args.db_path else None


@st.cache_data(show_spinner="Reading Phase 2 analytical views…")
def _load_bundle(path: str, include_partial: bool, modified_ns: int) -> dict[str, pd.DataFrame]:
    del modified_ns  # Included in the cache key so a newly committed report invalidates data.
    return queries.load_dashboard_bundle(path, include_partial=include_partial)


@st.cache_data(show_spinner=False)
def _load_audit_data(path: str, modified_ns: int) -> dict[str, pd.DataFrame]:
    del modified_ns
    return {
        "report_health": queries.load_report_health(path),
        "all_extraction_warnings": queries.load_all_extraction_warnings(path),
    }


def _sidebar(bundle: dict[str, pd.DataFrame], database_path: Path, include_partial: bool) -> tuple[str, DashboardContext]:
    reports = bundle["reports"].sort_values("report_date")
    earliest = reports["report_date"].min().date()
    latest = reports["report_date"].max().date()
    st.sidebar.markdown("## Earnings Insight")
    st.sidebar.caption("Phase 3 · Fundamental research")
    page = st.sidebar.radio("Research view", list(PAGES), key="navigation")
    st.sidebar.divider()
    st.sidebar.markdown("### Global filters")
    selected_range = st.sidebar.date_input(
        "Report date range",
        value=(earliest, latest),
        min_value=earliest,
        max_value=latest,
        key="global_date_range",
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start, end = selected_range
    else:
        start = end = selected_range if not isinstance(selected_range, tuple) else earliest
    options = date_options(reports, start, end)
    if not options:
        st.sidebar.error("No reports fall inside this range.")
        st.stop()
    selected = st.sidebar.selectbox(
        "FactSet report date",
        options,
        format_func=lambda value: pd.Timestamp(value).strftime("%Y-%m-%d"),
        key="global_report_date",
    )
    st.sidebar.caption("Latest allowed report is selected by default.")
    st.sidebar.divider()
    scope_label = "Safe + PARTIAL" if include_partial else "Safe reports only"
    st.sidebar.caption(f"Scope: {scope_label}")
    st.sidebar.caption(f"Database: {database_path.name}")
    context = DashboardContext(
        database_path=database_path,
        include_partial=include_partial,
        start_date=pd.Timestamp(start),
        end_date=pd.Timestamp(end),
        selected_report_date=pd.Timestamp(selected),
    )
    return page, context


def main() -> None:
    st.set_page_config(
        page_title="S&P 500 Earnings Momentum",
        page_icon=ui.PAGE_ICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ui.inject_css()
    requested_path = _command_line_database()
    database_path = requested_path or db.default_database_path()

    st.sidebar.markdown("### Data safety")
    include_partial = st.sidebar.checkbox(
        "Include partial reports",
        value=False,
        help="Off by default. When enabled, PARTIAL reports become selectable but missing observations remain missing.",
        key="include_partial",
    )
    try:
        contract = db.validate_database(database_path)
        bundle = _load_bundle(str(database_path), include_partial, database_path.stat().st_mtime_ns)
        bundle.update(_load_audit_data(str(database_path), database_path.stat().st_mtime_ns))
    except Exception as exc:
        st.error("The Phase 2 database could not be opened or does not satisfy the dashboard contract.")
        st.exception(exc)
        st.stop()

    page, context = _sidebar(bundle, database_path, include_partial)
    scoped_bundle = subset_bundle(bundle, context)
    # Date-range filters govern charts, but EPS momentum must retain enough
    # history to find valid 4W/13W comparisons outside the visible range.
    scoped_bundle["_full_bottom_up_eps"] = bundle["bottom_up_eps"]
    scoped_bundle["_full_index_metrics"] = bundle["index_metrics"]
    PAGES[page](scoped_bundle, context)
    st.divider()
    st.caption(
        f"Read-only SQLite · schema {contract.schema_version or 'unknown'} · "
        f"user_version {contract.user_version} · no interpolation or zero-filling"
    )


if __name__ == "__main__":
    main()
