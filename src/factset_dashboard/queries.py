"""Whitelisted Phase 2 queries with one centralized report-safety policy."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Final

import pandas as pd

from .db import DatabasePath, connect_readonly


PUBLIC_VIEW_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "v_reports": (
        "report_id",
        "sha256",
        "report_date",
        "filename",
        "filename_date",
        "source_file_path",
        "page_count",
        "extraction_timestamp",
        "extractor_version",
        "schema_version",
        "manifest_record_json",
        "status",
        "phase3_report_safe",
    ),
    "v_index_metrics": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "forward_12m_pe",
        "forward_12m_pe_5y_avg",
        "forward_12m_pe_10y_avg",
        "trailing_12m_pe",
        "trailing_12m_pe_5y_avg",
        "trailing_12m_pe_10y_avg",
        "reported_forward_12m_eps",
        "derived_forward_12m_eps",
        "valuation_reference_price",
        "valuation_as_of_date",
        "forward_eps_derivation_method",
        "current_quarter_period",
        "current_quarter_earnings_growth_pct",
        "current_quarter_revenue_growth_pct",
        "next_quarter_period",
        "next_quarter_earnings_growth_pct",
        "next_quarter_revenue_growth_pct",
        "following_quarter_period",
        "following_quarter_earnings_growth_pct",
        "following_quarter_revenue_growth_pct",
        "near_year_period",
        "near_year_earnings_growth_pct",
        "near_year_revenue_growth_pct",
        "far_year_period",
        "far_year_earnings_growth_pct",
        "far_year_revenue_growth_pct",
        "current_net_profit_margin_pct",
        "year_ago_net_profit_margin_pct",
        "five_year_avg_net_profit_margin_pct",
    ),
    "v_bottom_up_eps": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "period",
        "period_type",
        "calendar_year",
        "calendar_quarter",
        "eps",
        "confidence",
    ),
    "v_period_growth": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "period",
        "period_type",
        "estimate_status",
        "earnings_growth_pct",
        "revenue_growth_pct",
        "observation_as_of_date",
        "anchor_date",
    ),
    "v_sector_growth": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "period",
        "period_type",
        "estimate_status",
        "sector",
        "earnings_growth_pct",
        "revenue_growth_pct",
        "observation_as_of_date",
        "anchor_date",
    ),
    "v_sector_leadership": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "sector",
        "near_year_period",
        "far_year_period",
        "horizon_roll_flag",
        "near_relative_growth_spread_pp",
        "far_relative_growth_spread_pp",
        "relative_growth_transition_pp",
        "classification",
        "data_quality",
        "calculation_version",
    ),
    "v_sector_margin": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "sector",
        "current_net_profit_margin_pct",
        "year_ago_net_profit_margin_pct",
        "five_year_avg_net_profit_margin_pct",
        "margin_yoy_change_pp",
        "margin_vs_5y_pp",
        "observation_as_of_date",
    ),
    "v_sector_valuation": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "sector",
        "forward_12m_pe",
        "five_year_avg_forward_pe",
        "ten_year_avg_forward_pe",
        "premium_to_5y_pct",
        "premium_to_10y_pct",
        "observation_as_of_date",
    ),
    "v_eps_revisions": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "period",
        "period_type",
        "metric",
        "revision_window",
        "chart_scope",
        "company",
        "direction",
        "revision_pct",
        "rank",
        "observation_as_of_date",
        "anchor_date",
    ),
    "v_guidance": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "period",
        "period_type",
        "scope",
        "sector",
        "positive_count",
        "negative_count",
        "positive_pct",
        "negative_pct",
        "historical_5y_negative_guidance_avg_pct",
        "historical_10y_negative_guidance_avg_pct",
        "observation_as_of_date",
        "anchor_date",
    ),
    "v_surprises": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "period",
        "positive_eps_surprise_pct",
        "positive_revenue_surprise_pct",
        "eps_surprise_magnitude_pct",
        "revenue_surprise_magnitude_pct",
        "eps_5y_comparison_pct",
        "eps_10y_comparison_pct",
        "revenue_5y_comparison_pct",
        "revenue_10y_comparison_pct",
        "observation_as_of_date",
    ),
    "v_target_prices": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "bottom_up_target_price",
        "target_section_sp500_price",
        "implied_upside_pct",
        "buy_rating_pct",
        "hold_rating_pct",
        "sell_rating_pct",
        "buy_rating_count",
        "hold_rating_count",
        "sell_rating_count",
        "observation_as_of_date",
    ),
    "v_sector_target_prices": (
        "report_id",
        "report_date",
        "source_filename",
        "status",
        "sector",
        "implied_upside_pct",
    ),
    "v_observation_provenance": (
        "report_date",
        "source_filename",
        "report_id",
        "table_name",
        "observation_key",
        "field_name",
        "provenance_id",
        "source_page",
        "section_title",
        "chart_title",
        "raw_text",
        "raw_label",
        "extraction_method",
        "confidence",
    ),
}

VIEW_ORDER_BY: Final[dict[str, tuple[str, ...]]] = {
    "v_reports": ("report_date", "report_id"),
    "v_index_metrics": ("report_date", "report_id"),
    "v_bottom_up_eps": ("report_date", "period_type", "period"),
    "v_period_growth": ("report_date", "period_type", "period"),
    "v_sector_growth": ("report_date", "period_type", "period", "sector"),
    "v_sector_leadership": ("report_date", "sector"),
    "v_sector_margin": ("report_date", "sector"),
    "v_sector_valuation": ("report_date", "sector"),
    "v_eps_revisions": ("report_date", "direction", "rank"),
    "v_guidance": ("report_date", "scope", "sector", "period"),
    "v_surprises": ("report_date", "report_id"),
    "v_target_prices": ("report_date", "report_id"),
    "v_sector_target_prices": ("report_date", "sector"),
    "v_observation_provenance": (
        "report_date",
        "table_name",
        "observation_key",
        "field_name",
        "source_page",
    ),
}

DATE_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "report_date",
        "filename_date",
        "extraction_timestamp",
        "valuation_as_of_date",
        "observation_as_of_date",
        "anchor_date",
    }
)


def _safety_clause(include_partial: bool) -> tuple[str, tuple[object, ...]]:
    if include_partial:
        return "r.status IN (?, ?, ?)", (
            "SUCCESS",
            "SUCCESS_WITH_WARNINGS",
            "PARTIAL",
        )
    return "r.phase3_report_safe = ?", (1,)


def _normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    for column in DATE_COLUMNS.intersection(frame.columns):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def _load_public_view(
    connection: sqlite3.Connection,
    view_name: str,
    *,
    include_partial: bool,
) -> pd.DataFrame:
    columns = PUBLIC_VIEW_COLUMNS[view_name]
    selected = ", ".join(f'v."{column}" AS "{column}"' for column in columns)
    safety_sql, params = _safety_clause(include_partial)

    if view_name == "v_reports":
        selected = ", ".join(f'r."{column}" AS "{column}"' for column in columns)
        from_sql = "v_reports AS r"
    else:
        from_sql = f'{view_name} AS v JOIN v_reports AS r ON r.report_id = v.report_id'

    order_by = ", ".join(f'v."{column}"' for column in VIEW_ORDER_BY[view_name])
    if view_name == "v_reports":
        order_by = ", ".join(f'r."{column}"' for column in VIEW_ORDER_BY[view_name])
    sql = f"SELECT {selected} FROM {from_sql} WHERE {safety_sql} ORDER BY {order_by}"
    return _normalize_dates(pd.read_sql_query(sql, connection, params=params))


def _load(db_path: DatabasePath | None, view: str, include_partial: bool) -> pd.DataFrame:
    with connect_readonly(db_path) as connection:
        return _load_public_view(connection, view, include_partial=include_partial)


def load_reports(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_reports", include_partial)


def _load_report_health(connection: sqlite3.Connection) -> pd.DataFrame:
    columns = PUBLIC_VIEW_COLUMNS["v_reports"]
    selected = ", ".join(f'r."{column}" AS "{column}"' for column in columns)
    sql = f"SELECT {selected} FROM v_reports AS r ORDER BY r.report_date, r.report_id"
    return _normalize_dates(pd.read_sql_query(sql, connection))


def load_report_health(db_path: DatabasePath | None = None) -> pd.DataFrame:
    """Load every report status for the audit page, including FAILED rows."""

    with connect_readonly(db_path) as connection:
        return _load_report_health(connection)


def load_index_metrics(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_index_metrics", include_partial)


def load_bottom_up_eps(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_bottom_up_eps", include_partial)


def load_period_growth(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_period_growth", include_partial)


def load_sector_growth(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_sector_growth", include_partial)


def load_sector_leadership(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_sector_leadership", include_partial)


def load_sector_margin(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_sector_margin", include_partial)


def load_sector_valuation(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_sector_valuation", include_partial)


def load_eps_revisions(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_eps_revisions", include_partial)


def load_guidance(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_guidance", include_partial)


def load_surprises(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_surprises", include_partial)


def load_target_prices(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_target_prices", include_partial)


def load_sector_target_prices(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_sector_target_prices", include_partial)


def load_observation_provenance(db_path: DatabasePath | None = None, include_partial: bool = False) -> pd.DataFrame:
    return _load(db_path, "v_observation_provenance", include_partial)


def _load_extraction_warnings(
    connection: sqlite3.Connection,
    *,
    include_partial: bool,
) -> pd.DataFrame:
    safety_sql, params = _safety_clause(include_partial)
    sql = f"""
        SELECT
            r.report_id AS report_id,
            r.report_date AS report_date,
            r.filename AS source_filename,
            r.status AS status,
            w.ordinal AS ordinal,
            w.code AS code,
            w.severity AS severity,
            w.message AS message,
            w.context_json AS context_json
        FROM extraction_warnings AS w
        JOIN v_reports AS r ON r.report_id = w.report_id
        WHERE {safety_sql}
        ORDER BY r.report_date, w.ordinal
    """
    return _normalize_dates(pd.read_sql_query(sql, connection, params=params))


def load_extraction_warnings(
    db_path: DatabasePath | None = None,
    include_partial: bool = False,
) -> pd.DataFrame:
    with connect_readonly(db_path) as connection:
        return _load_extraction_warnings(connection, include_partial=include_partial)


def _load_all_extraction_warnings(connection: sqlite3.Connection) -> pd.DataFrame:
    sql = """
        SELECT
            r.report_id AS report_id,
            r.report_date AS report_date,
            r.filename AS source_filename,
            r.status AS status,
            w.ordinal AS ordinal,
            w.code AS code,
            w.severity AS severity,
            w.message AS message,
            w.context_json AS context_json
        FROM extraction_warnings AS w
        JOIN v_reports AS r ON r.report_id = w.report_id
        ORDER BY r.report_date, w.ordinal
    """
    return _normalize_dates(pd.read_sql_query(sql, connection))


def load_all_extraction_warnings(db_path: DatabasePath | None = None) -> pd.DataFrame:
    """Load warnings for every report for the audit page."""

    with connect_readonly(db_path) as connection:
        return _load_all_extraction_warnings(connection)


def load_dashboard_bundle(
    db_path: DatabasePath | None = None,
    include_partial: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load one coherent dashboard snapshot through a single connection."""

    with connect_readonly(db_path) as connection:
        bundle = {
            view.removeprefix("v_"): _load_public_view(
                connection,
                view,
                include_partial=include_partial,
            )
            for view in PUBLIC_VIEW_COLUMNS
        }
        bundle["extraction_warnings"] = _load_extraction_warnings(
            connection,
            include_partial=include_partial,
        )
    return bundle


LOADERS: Final[dict[str, Callable[..., pd.DataFrame]]] = {
    "reports": load_reports,
    "report_health": load_report_health,
    "index_metrics": load_index_metrics,
    "bottom_up_eps": load_bottom_up_eps,
    "period_growth": load_period_growth,
    "sector_growth": load_sector_growth,
    "sector_leadership": load_sector_leadership,
    "sector_margin": load_sector_margin,
    "sector_valuation": load_sector_valuation,
    "eps_revisions": load_eps_revisions,
    "guidance": load_guidance,
    "surprises": load_surprises,
    "target_prices": load_target_prices,
    "sector_target_prices": load_sector_target_prices,
    "observation_provenance": load_observation_provenance,
    "extraction_warnings": load_extraction_warnings,
    "all_extraction_warnings": load_all_extraction_warnings,
}
