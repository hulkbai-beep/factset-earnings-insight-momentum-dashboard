"""Shared filter state and DataFrame filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DashboardContext:
    database_path: Path
    include_partial: bool
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    selected_report_date: pd.Timestamp

    @property
    def selected_date_string(self) -> str:
        return self.selected_report_date.strftime("%Y-%m-%d")


def normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("report_date", "observation_as_of_date", "anchor_date", "valuation_as_of_date"):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce")
    return result


def apply_date_range(frame: pd.DataFrame, start: date | pd.Timestamp, end: date | pd.Timestamp) -> pd.DataFrame:
    if frame.empty or "report_date" not in frame.columns:
        return frame.copy()
    result = normalize_dates(frame)
    start_ts = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    return result.loc[result["report_date"].between(start_ts, end_ts)].copy()


def at_report_date(frame: pd.DataFrame, report_date: date | pd.Timestamp | str) -> pd.DataFrame:
    if frame.empty or "report_date" not in frame.columns:
        return frame.iloc[0:0].copy()
    result = normalize_dates(frame)
    target = pd.Timestamp(report_date).normalize()
    return result.loc[result["report_date"].dt.normalize().eq(target)].copy()


def date_options(reports: pd.DataFrame, start: date | pd.Timestamp, end: date | pd.Timestamp) -> list[pd.Timestamp]:
    scoped = apply_date_range(reports, start, end)
    if scoped.empty:
        return []
    return sorted(scoped["report_date"].dropna().dt.normalize().unique(), reverse=True)


def subset_bundle(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> dict[str, pd.DataFrame]:
    return {
        name: apply_date_range(frame, context.start_date, context.end_date)
        if isinstance(frame, pd.DataFrame)
        else frame
        for name, frame in bundle.items()
    }
