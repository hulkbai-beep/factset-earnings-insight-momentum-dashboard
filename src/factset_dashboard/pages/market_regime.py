"""Market Regime landing page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import charts, market_data, metrics, models, ui
from factset_dashboard.filters import DashboardContext, at_report_date


@st.cache_data(ttl=300, show_spinner=False)
def _load_spx_quote() -> market_data.MarketQuote | None:
    """Cache the external quote briefly and fail without blocking the page."""

    try:
        return market_data.fetch_yahoo_spx_quote()
    except market_data.MarketDataError:
        return None


def _snapshot(frame: pd.DataFrame, report_date: pd.Timestamp) -> pd.Series:
    current = at_report_date(frame, report_date)
    return current.iloc[-1] if not current.empty else pd.Series(dtype=object)


def _eps_cards(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> tuple[str, ...]:
    eps = bundle.get("_full_bottom_up_eps", bundle["bottom_up_eps"])
    index_metrics = bundle.get("_full_index_metrics", bundle["index_metrics"])
    periods = metrics.select_relevant_eps_periods(
        eps,
        index_metrics,
        as_of_date=context.selected_report_date,
    )
    momentum = metrics.calculate_eps_momentum(eps)
    columns = st.columns(max(2, len(periods)))
    if not periods:
        ui.note("No current or future calendar-year EPS observations are available.", quality=True)
        return periods
    for column, period in zip(columns, periods):
        current = momentum.loc[
            momentum["period"].eq(period)
            & momentum["report_date"].dt.normalize().eq(context.selected_report_date.normalize())
        ]
        row = current.iloc[-1] if not current.empty else pd.Series(dtype=object)
        with column:
            st.metric(period, ui.format_value(row.get("eps"), "eps"))
            st.caption(
                " · ".join(
                    [
                        f"1P {ui.format_delta(row.get('change_1p_pct')) or 'N/A'}",
                        f"4W {ui.format_delta(row.get('change_4w_pct')) or 'N/A'}",
                        f"13W {ui.format_delta(row.get('change_13w_pct')) or 'N/A'}",
                    ]
                )
            )
    return periods


def _market_price_overlay(
    bundle: dict[str, pd.DataFrame],
    context: DashboardContext,
) -> market_data.MarketQuote | None:
    st.subheader("Market price overlay")
    quote = _load_spx_quote()
    quote_column, reference_column = st.columns(2)

    with quote_column:
        if quote is None:
            st.metric("SPX latest available", "N/A")
            st.caption(
                "Yahoo Finance `^GSPC` is temporarily unavailable. The FactSet dashboard remains usable."
            )
        else:
            day_delta = quote.day_change_pct
            delta = (
                f"{day_delta:+.2f}% vs prior close"
                if day_delta is not None
                else None
            )
            st.metric("SPX latest available", f"{quote.price:,.2f}", delta)
            st.caption(
                f"[Yahoo Finance `{quote.symbol}`]({market_data.YAHOO_SPX_PAGE_URL}) · "
                f"{quote.currency} · as of {quote.as_of_label()}"
            )

    target_prices = bundle.get("target_prices", pd.DataFrame())
    reference = _snapshot(target_prices, context.selected_report_date)
    reference_price = ui.safe_float(reference.get("target_section_sp500_price"))
    with reference_column:
        if reference_price is None:
            st.metric("Selected FactSet price reference", "N/A")
        else:
            change = None
            if quote is not None and reference_price != 0:
                change = (quote.price / reference_price - 1.0) * 100.0
            delta = (
                f"{change:+.2f}% latest vs reference"
                if change is not None
                else None
            )
            st.metric(
                "Selected FactSet price reference",
                f"{reference_price:,.2f}",
                delta,
                delta_color="off",
            )
        st.caption(
            f"Reference published in the selected {context.selected_date_string} FactSet report."
        )

    st.caption(
        "Yahoo market data is an external, informational overlay and may be delayed. "
        "It is cached for five minutes and is never written to the canonical FactSet SQLite database."
    )
    return quote


def _valuation_scenario(
    bundle: dict[str, pd.DataFrame],
    context: DashboardContext,
    periods: tuple[str, ...],
    current_index_level: float | None,
) -> None:
    years = [period.removeprefix("CY") for period in periods]
    heading = "–".join(years) if years else "Forward"
    st.subheader(f"{heading} Valuation Scenario Range")
    st.caption(
        "Illustrative S&P 500 index levels = selected calendar-year bottom-up EPS × your P/E assumption. "
        "This is scenario analysis—not a price forecast, target price, or buy/sell signal."
    )

    index_metrics = bundle.get("_full_index_metrics", bundle["index_metrics"])
    defaults = metrics.default_valuation_multiples(
        index_metrics,
        as_of_date=context.selected_report_date,
    )
    current = _snapshot(index_metrics, context.selected_report_date)
    st.caption(
        "Observed valuation references for the selected report: "
        f"10Y average {ui.format_value(current.get('forward_12m_pe_10y_avg'), 'pe')} · "
        f"5Y average {ui.format_value(current.get('forward_12m_pe_5y_avg'), 'pe')} · "
        f"current forward {ui.format_value(current.get('forward_12m_pe'), 'pe')}. "
        "Defaults are these three references sorted from low to high."
    )
    if defaults is None:
        ui.note(
            "A complete set of current, five-year, and ten-year P/E references is required to initialize this scenario.",
            quality=True,
        )
        return

    input_columns = st.columns(3)
    with input_columns[0]:
        low_pe = st.number_input(
            "Low P/E assumption",
            min_value=0.1,
            value=float(defaults[0]),
            step=0.1,
            format="%.1f",
            key=f"valuation_scenario_low_pe_{context.selected_date_string}",
        )
    with input_columns[1]:
        base_pe = st.number_input(
            "Base P/E assumption",
            min_value=0.1,
            value=float(defaults[1]),
            step=0.1,
            format="%.1f",
            key=f"valuation_scenario_base_pe_{context.selected_date_string}",
        )
    with input_columns[2]:
        high_pe = st.number_input(
            "High P/E assumption",
            min_value=0.1,
            value=float(defaults[2]),
            step=0.1,
            format="%.1f",
            key=f"valuation_scenario_high_pe_{context.selected_date_string}",
        )

    if not low_pe <= base_pe <= high_pe:
        st.warning("Set the assumptions so Low P/E ≤ Base P/E ≤ High P/E.")
        return

    eps = bundle.get("_full_bottom_up_eps", bundle["bottom_up_eps"])
    scenarios = metrics.calculate_valuation_scenarios(
        eps,
        periods=periods,
        as_of_date=context.selected_report_date,
        low_pe=low_pe,
        base_pe=base_pe,
        high_pe=high_pe,
    )
    cards = st.columns(max(2, len(scenarios)))
    for column, row in zip(cards, scenarios.itertuples(index=False)):
        with column:
            low = ui.format_value(row.low_index_level, "price")
            high = ui.format_value(row.high_index_level, "price")
            st.metric(f"{row.period} scenario range", f"{low} – {high}")
            st.caption(
                f"Base {ui.format_value(row.base_index_level, 'price')} · "
                f"EPS {ui.format_value(row.eps, 'eps')}"
            )
    st.plotly_chart(
        charts.valuation_scenario_range_chart(
            scenarios,
            current_index_level=current_index_level,
        ),
        width="stretch",
    )


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "S&P 500 fundamental regime",
        "Market Regime",
        "A top-down read on estimate momentum, growth, margin quality, and valuation—ordered by research priority.",
    )
    report = _snapshot(bundle["reports"], context.selected_report_date)
    status = report.get("status", "N/A")
    st.caption(f"Selected FactSet report: {context.selected_date_string} · Status: {status}")

    spx_quote = _market_price_overlay(bundle, context)

    st.subheader("Bottom-up EPS momentum")
    periods = _eps_cards(bundle, context)
    st.caption("1P is the previous valid publication. 4W and 13W use date anchors with a 14-day staleness limit.")

    current = _snapshot(bundle["index_metrics"], context.selected_report_date)
    st.subheader("Growth outlook")
    growth_columns = st.columns(4)
    growth_cards = [
        (f"{current.get('near_year_period', 'Near year')} earnings", "near_year_earnings_growth_pct"),
        (f"{current.get('far_year_period', 'Far year')} earnings", "far_year_earnings_growth_pct"),
        (f"{current.get('current_quarter_period', 'Current qtr')} earnings", "current_quarter_earnings_growth_pct"),
        (f"{current.get('next_quarter_period', 'Next qtr')} earnings", "next_quarter_earnings_growth_pct"),
    ]
    for column, (label, field) in zip(growth_columns, growth_cards):
        with column:
            ui.metric_card(str(label), current.get(field), kind="pct")

    revenue_columns = st.columns(4)
    revenue_cards = [
        (f"{current.get('near_year_period', 'Near year')} revenue", "near_year_revenue_growth_pct"),
        (f"{current.get('far_year_period', 'Far year')} revenue", "far_year_revenue_growth_pct"),
        (f"{current.get('current_quarter_period', 'Current qtr')} revenue", "current_quarter_revenue_growth_pct"),
        (f"{current.get('next_quarter_period', 'Next qtr')} revenue", "next_quarter_revenue_growth_pct"),
    ]
    for column, (label, field) in zip(revenue_columns, revenue_cards):
        with column:
            ui.metric_card(str(label), current.get(field), kind="pct")

    margin_change = None
    if pd.notna(current.get("current_net_profit_margin_pct")) and pd.notna(current.get("year_ago_net_profit_margin_pct")):
        margin_change = float(current["current_net_profit_margin_pct"]) - float(current["year_ago_net_profit_margin_pct"])
    premiums = models.valuation_premiums(current)
    st.subheader("Margin & valuation")
    quality_columns = st.columns(4)
    cards = [
        ("Current net margin", current.get("current_net_profit_margin_pct"), "pct", None, "pp"),
        ("Year-ago margin", current.get("year_ago_net_profit_margin_pct"), "pct", None, "pp"),
        ("Margin expansion", margin_change, "pp", None, "pp"),
        ("Forward 12M P/E", current.get("forward_12m_pe"), "pe", None, "pct"),
    ]
    for column, (label, value, kind, delta, delta_kind) in zip(quality_columns, cards):
        with column:
            ui.metric_card(label, value, kind=kind, delta=delta, delta_kind=delta_kind)
    valuation_columns = st.columns(4)
    valuation_cards = [
        ("5Y average P/E", current.get("forward_12m_pe_5y_avg"), "pe"),
        ("Premium to 5Y", premiums["premium_to_5y_pct"], "pct"),
        ("10Y average P/E", current.get("forward_12m_pe_10y_avg"), "pe"),
        ("Premium to 10Y", premiums["premium_to_10y_pct"], "pct"),
    ]
    for column, (label, value, kind) in zip(valuation_columns, valuation_cards):
        with column:
            ui.metric_card(label, value, kind=kind)

    _valuation_scenario(
        bundle,
        context,
        periods,
        spx_quote.price if spx_quote is not None else None,
    )

    anomalies = models.detected_growth_provenance_anomalies(bundle["index_metrics"], bundle["observation_provenance"])
    if not anomalies.empty:
        dates = ", ".join(sorted(pd.to_datetime(anomalies["report_date"]).dt.strftime("%Y-%m-%d").unique()))
        ui.note(
            f"Data-quality alert: canonical near-year earnings growth conflicts with linked source prose on {dates}. The chart preserves the canonical value; review provenance before interpreting the move."
        )

    st.subheader("Bottom-up EPS estimate trend")
    eps_trend = models.eps_trend(bundle["bottom_up_eps"], list(periods))
    st.plotly_chart(
        charts.line_chart(
            eps_trend,
            x="report_date",
            series=[(period, period) for period in periods],
            y_title="Bottom-up EPS ($)",
            hover_suffix="",
        ),
        width="stretch",
    )

    roll_dates = metrics.horizon_roll_dates(bundle["sector_leadership"])
    horizon_history = models.market_horizon_regimes(bundle["index_metrics"], roll_dates)
    left, right = st.columns(2)
    with left:
        st.subheader("Earnings growth outlook")
        earnings_fig = charts.segmented_line_chart(
            horizon_history,
            x="report_date",
            segment="horizon_regime_id",
            series=[("near_year_earnings_growth_pct", "Near year"), ("far_year_earnings_growth_pct", "Far year")],
            y_title="Earnings growth (%)",
            hover_suffix="%",
        )
        charts.add_horizon_roll_markers(earnings_fig, roll_dates)
        st.plotly_chart(earnings_fig, width="stretch")
    with right:
        st.subheader("Revenue growth outlook")
        revenue_fig = charts.segmented_line_chart(
            horizon_history,
            x="report_date",
            segment="horizon_regime_id",
            series=[("near_year_revenue_growth_pct", "Near year"), ("far_year_revenue_growth_pct", "Far year")],
            y_title="Revenue growth (%)",
            hover_suffix="%",
        )
        charts.add_horizon_roll_markers(revenue_fig, roll_dates)
        st.plotly_chart(revenue_fig, width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Net margin trend")
        st.plotly_chart(
            charts.line_chart(
                bundle["index_metrics"],
                x="report_date",
                series=[
                    ("current_net_profit_margin_pct", "Current margin"),
                    ("year_ago_net_profit_margin_pct", "Year-ago margin"),
                ],
                y_title="Net profit margin (%)",
                hover_suffix="%",
            ),
            width="stretch",
        )
    with right:
        st.subheader("Forward 12M P/E")
        st.plotly_chart(
            charts.line_chart(
                bundle["index_metrics"],
                x="report_date",
                series=[
                    ("forward_12m_pe", "Forward 12M P/E"),
                    ("forward_12m_pe_5y_avg", "5Y average"),
                    ("forward_12m_pe_10y_avg", "10Y average"),
                ],
                y_title="P/E multiple (×)",
                hover_suffix="×",
            ),
            width="stretch",
        )
