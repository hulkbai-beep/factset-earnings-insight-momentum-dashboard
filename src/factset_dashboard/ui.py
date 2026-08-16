"""Shared presentation helpers for the Streamlit application."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import streamlit as st


PAGE_ICON = "◈"


def inject_css() -> None:
    """Apply the restrained visual language used across every dashboard page."""

    st.markdown(
        """
        <style>
        :root {
          --ink: #12212f;
          --muted: #647482;
          --line: #dce4e9;
          --paper: #f7f9fa;
          --teal: #0f766e;
          --gold: #b7791f;
        }
        .stApp { background: linear-gradient(180deg, #f8fafb 0, #ffffff 260px); }
        [data-testid="stSidebar"] { background: #102433; }
        [data-testid="stSidebar"] * { color: #eef4f6; }
        [data-testid="stSidebar"] [data-baseweb="select"] * { color: #12212f; }
        [data-testid="stSidebar"] input { color: #12212f; }
        [data-testid="stMetric"] {
          background: rgba(255,255,255,.92);
          border: 1px solid var(--line);
          border-radius: 10px;
          padding: .85rem 1rem;
          box-shadow: 0 5px 20px rgba(22, 40, 52, .04);
        }
        [data-testid="stMetricLabel"] { color: var(--muted); }
        [data-testid="stMetricValue"] { color: var(--ink); }
        h1, h2, h3 { color: var(--ink); letter-spacing: -.018em; }
        h1 { border-bottom: 1px solid var(--line); padding-bottom: .55rem; }
        .eyebrow {
          color: var(--teal); font-size: .75rem; font-weight: 700;
          letter-spacing: .11em; text-transform: uppercase; margin-bottom: .15rem;
        }
        .page-intro { color: var(--muted); max-width: 920px; margin: -.35rem 0 1.25rem; }
        .research-note {
          border-left: 3px solid var(--gold); background: #fffaf0;
          color: #4a4030; padding: .7rem .9rem; border-radius: 0 7px 7px 0;
          margin: .4rem 0 1rem;
        }
        .quality-note {
          border-left: 3px solid var(--teal); background: #eef8f7;
          color: #294b49; padding: .7rem .9rem; border-radius: 0 7px 7px 0;
          margin: .4rem 0 1rem;
        }
        .small-muted { color: var(--muted); font-size: .82rem; }
        div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, intro: str) -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="page-intro">{intro}</div>', unsafe_allow_html=True)


def note(text: str, *, quality: bool = False) -> None:
    css_class = "quality-note" if quality else "research-note"
    st.markdown(f'<div class="{css_class}">{text}</div>', unsafe_allow_html=True)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def format_value(value: Any, kind: str = "number", digits: int = 1) -> str:
    """Format values without ever turning missing observations into zero."""

    if is_missing(value):
        return "N/A"
    numeric = float(value)
    if kind == "eps":
        return f"${numeric:,.2f}"
    if kind == "pct":
        return f"{numeric:,.{digits}f}%"
    if kind == "pp":
        return f"{numeric:+,.{digits}f} pp"
    if kind == "pe":
        return f"{numeric:,.{digits}f}×"
    if kind == "price":
        return f"{numeric:,.0f}"
    if kind == "count":
        return f"{int(numeric):,}"
    return f"{numeric:,.{digits}f}"


def format_delta(value: Any, kind: str = "pct", digits: int = 1) -> str | None:
    if is_missing(value):
        return None
    numeric = float(value)
    suffix = "%" if kind == "pct" else " pp"
    return f"{numeric:+,.{digits}f}{suffix}"


def metric_card(
    label: str,
    value: Any,
    *,
    kind: str = "number",
    delta: Any = None,
    delta_kind: str = "pct",
    help_text: str | None = None,
    inverse_delta: bool = False,
) -> None:
    st.metric(
        label,
        format_value(value, kind),
        format_delta(delta, delta_kind),
        help=help_text,
        delta_color="inverse" if inverse_delta else "normal",
    )


def dataframe_for_display(frame: pd.DataFrame, formats: dict[str, str] | None = None) -> pd.DataFrame:
    """Return a display copy with honest N/A values and stable date strings."""

    result = frame.copy()
    formats = formats or {}
    for column in result.columns:
        if pd.api.types.is_datetime64_any_dtype(result[column]):
            result[column] = result[column].dt.strftime("%Y-%m-%d")
    for column, kind in formats.items():
        if column in result.columns:
            result[column] = result[column].map(lambda value: format_value(value, kind))
    result = result.astype(object)
    return result.where(pd.notna(result), "N/A")


def available_count(frame: pd.DataFrame, columns: list[str]) -> tuple[int, int]:
    if frame.empty:
        return 0, 0
    mask = frame[columns].notna().all(axis=1)
    return int(mask.sum()), int(len(frame))


def safe_float(value: Any) -> float | None:
    if is_missing(value):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None
