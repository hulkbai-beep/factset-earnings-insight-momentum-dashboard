"""Plotly chart builders with consistent financial-research styling."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = {
    "navy": "#17324d",
    "teal": "#0f766e",
    "teal_light": "#74b7b1",
    "gold": "#b7791f",
    "red": "#b94a48",
    "slate": "#647482",
    "line": "#dce4e9",
    "paper": "#ffffff",
}

SERIES_COLORS = [
    COLORS["teal"],
    COLORS["navy"],
    COLORS["gold"],
    "#6b5ca5",
    "#3d7ea6",
    "#a65d57",
    "#5f7f61",
    "#d08b3e",
    "#577590",
    "#8f6f8f",
    "#4f8f8b",
]

CLASSIFICATION_COLORS = {
    "PERSISTENT_LEADER": "#157f74",
    "EMERGING_LEADER": "#6aaa64",
    "FADING_LEADER": "#d09a3d",
    "PERSISTENT_LAGGARD": "#b6534f",
}

CLASSIFICATION_LABELS = {
    "PERSISTENT_LEADER": "Persistent leader",
    "EMERGING_LEADER": "Emerging leader",
    "FADING_LEADER": "Fading leader",
    "PERSISTENT_LAGGARD": "Persistent laggard",
}


def _base_layout(fig: go.Figure, *, height: int = 430, legend: bool = True) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=26, r=20, t=46, b=28),
        paper_bgcolor=COLORS["paper"],
        plot_bgcolor=COLORS["paper"],
        colorway=SERIES_COLORS,
        hovermode="x unified",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        font=dict(family="Inter, Segoe UI, Arial", color="#253746"),
    )
    fig.update_xaxes(showgrid=False, linecolor=COLORS["line"], tickformat="%b %d")
    fig.update_yaxes(gridcolor="#edf1f3", zerolinecolor=COLORS["line"])
    return fig


def empty_figure(message: str, *, height: int = 360) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(color=COLORS["slate"], size=14),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base_layout(fig, height=height, legend=False)


def line_chart(
    frame: pd.DataFrame,
    *,
    x: str,
    series: Sequence[tuple[str, str]],
    y_title: str,
    hover_suffix: str = "",
    height: int = 430,
    markers: bool = True,
) -> go.Figure:
    if frame.empty or not any(column in frame and frame[column].notna().any() for column, _ in series):
        return empty_figure("No observations are available for the selected filters.", height=height)
    fig = go.Figure()
    for index, (column, label) in enumerate(series):
        if column not in frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame[x],
                y=frame[column],
                name=label,
                mode="lines+markers" if markers else "lines",
                connectgaps=False,
                line=dict(width=2.4, color=SERIES_COLORS[index % len(SERIES_COLORS)]),
                marker=dict(size=6),
                hovertemplate=f"%{{y:.2f}}{hover_suffix}<extra>{label}</extra>",
            )
        )
    _base_layout(fig, height=height)
    fig.update_yaxes(title=y_title)
    return fig


def segmented_line_chart(
    frame: pd.DataFrame,
    *,
    x: str,
    segment: str,
    series: Sequence[tuple[str, str]],
    y_title: str,
    hover_suffix: str = "",
    height: int = 430,
) -> go.Figure:
    """Draw one trace per regime so no line crosses a forecast-horizon roll."""

    if frame.empty or segment not in frame:
        return empty_figure("No observations are available for the selected filters.", height=height)
    fig = go.Figure()
    for series_index, (column, label) in enumerate(series):
        if column not in frame:
            continue
        for group_index, (_, group) in enumerate(frame.groupby(segment, sort=True, dropna=False)):
            fig.add_trace(
                go.Scatter(
                    x=group[x],
                    y=group[column],
                    name=label,
                    legendgroup=label,
                    showlegend=group_index == 0,
                    mode="lines+markers",
                    connectgaps=False,
                    line=dict(width=2.4, color=SERIES_COLORS[series_index % len(SERIES_COLORS)]),
                    marker=dict(size=6),
                    hovertemplate=f"%{{y:.2f}}{hover_suffix}<extra>{label}</extra>",
                )
            )
    if not fig.data:
        return empty_figure("No observations are available for the selected filters.", height=height)
    _base_layout(fig, height=height)
    fig.update_yaxes(title=y_title)
    return fig


def valuation_scenario_range_chart(
    frame: pd.DataFrame,
    *,
    current_index_level: float | None = None,
    height: int = 390,
) -> go.Figure:
    """Show low-to-high index-level ranges with the base scenario emphasized."""

    required = [
        "period",
        "eps",
        "low_pe",
        "base_pe",
        "high_pe",
        "low_index_level",
        "base_index_level",
        "high_index_level",
    ]
    available = (
        frame.dropna(subset=required).copy()
        if all(column in frame for column in required)
        else pd.DataFrame()
    )
    if available.empty:
        return empty_figure(
            "No complete EPS and valuation scenario inputs are available for this report.",
            height=height,
        )

    base = pd.to_numeric(available["base_index_level"], errors="coerce")
    low = pd.to_numeric(available["low_index_level"], errors="coerce")
    high = pd.to_numeric(available["high_index_level"], errors="coerce")
    custom = available[
        [
            "eps",
            "low_pe",
            "base_pe",
            "high_pe",
            "low_index_level",
            "high_index_level",
        ]
    ].to_numpy()
    fig = go.Figure(
        go.Scatter(
            x=available["period"],
            y=base,
            mode="markers+text",
            name="Base scenario",
            marker=dict(size=15, color=COLORS["gold"], line=dict(width=2, color="white")),
            error_y=dict(
                type="data",
                symmetric=False,
                array=(high - base).tolist(),
                arrayminus=(base - low).tolist(),
                color=COLORS["teal"],
                thickness=5,
                width=18,
            ),
            text=[f"{value:,.0f}" for value in base],
            textposition="middle right",
            customdata=custom,
            hovertemplate=(
                "<b>%{x}</b><br>Bottom-up EPS: $%{customdata[0]:,.2f}"
                "<br>Low: %{customdata[4]:,.0f} at %{customdata[1]:.1f}×"
                "<br>Base: %{y:,.0f} at %{customdata[2]:.1f}×"
                "<br>High: %{customdata[5]:,.0f} at %{customdata[3]:.1f}×"
                "<extra></extra>"
            ),
        )
    )
    _base_layout(fig, height=height, legend=False)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title="Calendar-year EPS period", tickformat=None)
    fig.update_yaxes(title="Illustrative S&P 500 index level", tickformat=",")
    if current_index_level is not None and pd.notna(current_index_level):
        level = float(current_index_level)
        if level > 0:
            fig.add_hline(
                y=level,
                line_width=2,
                line_dash="dot",
                line_color=COLORS["navy"],
                annotation_text=f"Latest SPX {level:,.2f}",
                annotation_position="top left",
                annotation_font_color=COLORS["navy"],
            )
    return fig


def add_horizon_roll_markers(fig: go.Figure, roll_dates: Iterable[pd.Timestamp | str]) -> go.Figure:
    for index, roll_date in enumerate(sorted(set(pd.Timestamp(value) for value in roll_dates))):
        fig.add_vline(x=roll_date, line_width=1.5, line_dash="dash", line_color=COLORS["gold"])
        fig.add_annotation(
            x=roll_date,
            y=1,
            yref="paper",
            text="Forecast horizon roll" if index == 0 else "Horizon roll",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font=dict(size=10, color=COLORS["gold"]),
        )
    return fig


def leadership_quadrant(frame: pd.DataFrame) -> go.Figure:
    required = ["near_relative_growth_spread_pp", "far_relative_growth_spread_pp", "sector"]
    available = frame.dropna(subset=required).copy() if all(c in frame for c in required) else pd.DataFrame()
    if available.empty:
        return empty_figure("No complete sector leadership observations are available for this report date.", height=570)
    available["classification_label"] = available["classification"].map(CLASSIFICATION_LABELS).fillna("Unavailable")
    label_colors = {
        CLASSIFICATION_LABELS[key]: value for key, value in CLASSIFICATION_COLORS.items()
    }
    fig = px.scatter(
        available,
        x="near_relative_growth_spread_pp",
        y="far_relative_growth_spread_pp",
        text="sector",
        color="classification_label",
        color_discrete_map=label_colors,
        custom_data=[
            "sector",
            "near_year_period",
            "far_year_period",
            "relative_growth_transition_pp",
            "classification_label",
            "data_quality",
        ],
    )
    fig.update_traces(
        marker=dict(size=15, line=dict(width=1.5, color="white")),
        textposition="top center",
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>Near (%{customdata[1]}): %{x:.1f} pp"
            "<br>Far (%{customdata[2]}): %{y:.1f} pp"
            "<br>Transition: %{customdata[3]:+.1f} pp"
            "<br>Regime: %{customdata[4]}<br>Quality: %{customdata[5]}<extra></extra>"
        ),
    )
    fig.add_hline(y=0, line_color=COLORS["slate"], line_width=1)
    fig.add_vline(x=0, line_color=COLORS["slate"], line_width=1)
    labels = [
        (0.98, 0.98, "Persistent leaders", "right", "top"),
        (0.02, 0.98, "Emerging leaders", "left", "top"),
        (0.98, 0.02, "Fading leaders", "right", "bottom"),
        (0.02, 0.02, "Persistent laggards", "left", "bottom"),
    ]
    for x, y, text, xanchor, yanchor in labels:
        fig.add_annotation(
            x=x,
            y=y,
            xref="paper",
            yref="paper",
            text=text,
            showarrow=False,
            xanchor=xanchor,
            yanchor=yanchor,
            font=dict(size=11, color=COLORS["slate"]),
        )
    _base_layout(fig, height=570)
    fig.update_layout(hovermode="closest", legend_title_text="Regime")
    fig.update_xaxes(title="Near-year growth spread vs S&P 500 (pp)")
    fig.update_yaxes(title="Far-year growth spread vs S&P 500 (pp)")
    return fig


def leadership_heatmap(
    frame: pd.DataFrame,
    roll_dates: Iterable[pd.Timestamp | str],
    *,
    report_dates: Iterable[pd.Timestamp | str] | None = None,
) -> go.Figure:
    if frame.empty:
        return empty_figure("No leadership history is available for the selected date range.", height=470)
    ordered_classes = [
        "PERSISTENT_LAGGARD",
        "FADING_LEADER",
        "EMERGING_LEADER",
        "PERSISTENT_LEADER",
    ]
    mapping = {value: index for index, value in enumerate(ordered_classes)}
    working = frame.drop_duplicates(["sector", "report_date"], keep="last").copy()
    working["class_code"] = working["classification"].map(mapping)
    z = working.pivot(index="sector", columns="report_date", values="class_code")
    text = working.pivot(index="sector", columns="report_date", values="classification")
    if report_dates is not None:
        complete_dates = sorted({pd.Timestamp(value).normalize() for value in report_dates})
        z = z.reindex(columns=complete_dates)
        text = text.reindex(columns=complete_dates)
    text = text.reindex(index=z.index, columns=z.columns).replace(CLASSIFICATION_LABELS)
    colorscale = [
        [0.00, CLASSIFICATION_COLORS["PERSISTENT_LAGGARD"]],
        [0.24, CLASSIFICATION_COLORS["PERSISTENT_LAGGARD"]],
        [0.25, CLASSIFICATION_COLORS["FADING_LEADER"]],
        [0.49, CLASSIFICATION_COLORS["FADING_LEADER"]],
        [0.50, CLASSIFICATION_COLORS["EMERGING_LEADER"]],
        [0.74, CLASSIFICATION_COLORS["EMERGING_LEADER"]],
        [0.75, CLASSIFICATION_COLORS["PERSISTENT_LEADER"]],
        [1.00, CLASSIFICATION_COLORS["PERSISTENT_LEADER"]],
    ]
    fig = go.Figure(
        go.Heatmap(
            z=z.values,
            x=z.columns,
            y=z.index,
            text=text.values,
            zmin=0,
            zmax=3,
            colorscale=colorscale,
            showscale=False,
            hovertemplate="%{y}<br>%{x|%Y-%m-%d}<br>%{text}<extra></extra>",
            xgap=1,
            ygap=1,
        )
    )
    _base_layout(fig, height=470, legend=False)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title="FactSet report date", tickangle=-45)
    fig.update_yaxes(title=None, autorange="reversed")
    add_horizon_roll_markers(fig, roll_dates)
    return fig


def horizontal_bar(
    frame: pd.DataFrame,
    *,
    x: str,
    y: str,
    x_title: str,
    color: str | None = None,
    height: int = 440,
    hover_data: Sequence[str] | None = None,
) -> go.Figure:
    available = frame.dropna(subset=[x, y]).sort_values(x) if x in frame and y in frame else pd.DataFrame()
    if available.empty:
        return empty_figure("No observations are available for this ranking.", height=height)
    fig = px.bar(
        available,
        x=x,
        y=y,
        orientation="h",
        color=color,
        color_continuous_scale=[COLORS["red"], "#e6e9e8", COLORS["teal"]] if color else None,
        hover_data=list(hover_data or []),
    )
    fig.update_traces(marker_line_width=0, hovertemplate=None)
    _base_layout(fig, height=height, legend=False)
    fig.update_xaxes(title=x_title)
    fig.update_yaxes(title=None)
    if color:
        fig.update_layout(coloraxis_showscale=False)
    return fig


def opportunity_map(frame: pd.DataFrame) -> go.Figure:
    required = ["sector", "premium_to_5y_pct", "far_relative_growth_spread_pp"]
    available = frame.dropna(subset=required).copy() if all(c in frame for c in required) else pd.DataFrame()
    if available.empty:
        return empty_figure("No matched growth and valuation observations are available for this report.", height=560)
    fig = px.scatter(
        available,
        x="premium_to_5y_pct",
        y="far_relative_growth_spread_pp",
        text="sector",
        color="far_relative_growth_spread_pp",
        color_continuous_scale=[COLORS["red"], "#dfe7e6", COLORS["teal"]],
        custom_data=["sector", "forward_12m_pe", "far_year_period", "data_quality"],
    )
    fig.update_traces(
        marker=dict(size=16, line=dict(width=1.5, color="white")),
        textposition="top center",
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>Premium to 5Y: %{x:+.1f}%"
            "<br>Far growth spread (%{customdata[2]}): %{y:+.1f} pp"
            "<br>Forward P/E: %{customdata[1]:.1f}×<br>Quality: %{customdata[3]}<extra></extra>"
        ),
    )
    fig.add_hline(y=0, line_color=COLORS["slate"], line_width=1)
    fig.add_vline(x=0, line_color=COLORS["slate"], line_width=1)
    annotations = [
        (0.02, 0.98, "Growth + discount", "left", "top"),
        (0.98, 0.98, "Growth + premium", "right", "top"),
        (0.02, 0.02, "Weak growth + discount", "left", "bottom"),
        (0.98, 0.02, "Weak growth + premium", "right", "bottom"),
    ]
    for x, y, text, xanchor, yanchor in annotations:
        fig.add_annotation(
            x=x,
            y=y,
            xref="paper",
            yref="paper",
            text=text,
            showarrow=False,
            xanchor=xanchor,
            yanchor=yanchor,
            font=dict(size=11, color=COLORS["slate"]),
        )
    _base_layout(fig, height=560, legend=False)
    fig.update_layout(hovermode="closest", coloraxis_showscale=False)
    fig.update_xaxes(title="Premium / discount to sector 5Y P/E average (%)")
    fig.update_yaxes(title="Far-year growth spread vs S&P 500 (pp)")
    return fig


def entity_growth_chart(frame: pd.DataFrame, *, y_title: str) -> go.Figure:
    available = frame.dropna(subset=["report_date", "entity"]).copy()
    if available.empty or not available["growth_pct"].notna().any():
        return empty_figure("No matched growth observations are available for this period.")
    fig = px.line(
        available,
        x="report_date",
        y="growth_pct",
        color="entity",
        markers=True,
        color_discrete_sequence=SERIES_COLORS,
        custom_data=["entity", "period", "estimate_status"],
    )
    fig.update_traces(
        connectgaps=False,
        line=dict(width=2.3),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>%{x|%Y-%m-%d}<br>%{customdata[1]}: %{y:.1f}%"
            "<br>Status: %{customdata[2]}<extra></extra>"
        ),
    )
    _base_layout(fig)
    fig.update_yaxes(title=y_title, ticksuffix="%")
    fig.update_xaxes(title=None)
    return fig


def spread_chart(frame: pd.DataFrame, *, value_column: str = "relative_growth_spread_pp") -> go.Figure:
    available = frame.dropna(subset=["report_date", "sector"]).copy()
    if available.empty or not available[value_column].notna().any():
        return empty_figure("No same-report, same-period spread observations are available.")
    fig = px.line(
        available,
        x="report_date",
        y=value_column,
        color="sector",
        markers=True,
        color_discrete_sequence=SERIES_COLORS,
        custom_data=["sector", "period"],
    )
    fig.update_traces(
        connectgaps=False,
        line=dict(width=2.2),
        hovertemplate="<b>%{customdata[0]}</b><br>%{x|%Y-%m-%d}<br>%{customdata[1]}: %{y:+.1f} pp<extra></extra>",
    )
    fig.add_hline(y=0, line_color=COLORS["slate"], line_width=1)
    _base_layout(fig)
    fig.update_yaxes(title="Sector growth minus S&P 500 (pp)")
    return fig
