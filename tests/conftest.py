from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path

import pytest

from factset_dashboard.db import EXPECTED_USER_VERSION, default_database_path
from factset_dashboard.queries import PUBLIC_VIEW_COLUMNS


INTEGER_COLUMNS = {
    "report_id",
    "page_count",
    "phase3_report_safe",
    "calendar_year",
    "calendar_quarter",
    "horizon_roll_flag",
    "positive_count",
    "negative_count",
    "buy_rating_count",
    "hold_rating_count",
    "sell_rating_count",
    "rank",
    "source_page",
    "ordinal",
}
REAL_COLUMNS = {
    "eps",
    "forward_12m_pe",
    "forward_12m_pe_5y_avg",
    "forward_12m_pe_10y_avg",
    "trailing_12m_pe",
    "trailing_12m_pe_5y_avg",
    "trailing_12m_pe_10y_avg",
    "reported_forward_12m_eps",
    "derived_forward_12m_eps",
    "valuation_reference_price",
    "current_sp500_price",
    "bottom_up_target_price",
    "target_section_sp500_price",
}


def _sqlite_type(column: str) -> str:
    if column in INTEGER_COLUMNS or column.endswith("_count"):
        return "INTEGER"
    if (
        column in REAL_COLUMNS
        or column.endswith("_pct")
        or column.endswith("_pp")
        or column.endswith("_pe")
    ):
        return "REAL"
    return "TEXT"


def _insert_view_row(
    connection: sqlite3.Connection,
    view_name: str,
    values: Mapping[str, object],
) -> None:
    unknown = sorted(set(values) - set(PUBLIC_VIEW_COLUMNS[view_name]))
    if unknown:
        raise AssertionError(f"Unknown {view_name} fixture columns: {unknown}")
    columns = tuple(values)
    identifiers = ", ".join(f'"{column}"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    connection.execute(
        f'INSERT INTO "_fixture_{view_name}" ({identifiers}) VALUES ({placeholders})',
        tuple(values[column] for column in columns),
    )


def _report_row(
    report_id: int,
    report_date: str,
    status: str,
    phase3_report_safe: int,
) -> dict[str, object]:
    compact_date = report_date.replace("-", "")
    return {
        "report_id": report_id,
        "sha256": f"fixture-sha-{report_id}",
        "report_date": report_date,
        "filename": f"EarningsInsight_{compact_date}.pdf",
        "filename_date": report_date,
        "source_file_path": f"fixture/{report_id}.pdf",
        "page_count": 40,
        "extraction_timestamp": f"{report_date}T12:00:00Z",
        "extractor_version": "fixture",
        "schema_version": "2.1.0",
        "manifest_record_json": None,
        "status": status,
        "phase3_report_safe": phase3_report_safe,
    }


@pytest.fixture()
def phase3_db(tmp_path: Path) -> Path:
    """Create a deterministic, minimal implementation of the public view contract."""

    database = tmp_path / "phase3-contract.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(f"PRAGMA user_version = {EXPECTED_USER_VERSION}")
        connection.execute(
            "CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_metadata(key, value) VALUES ('schema_version', '2.1.0')"
        )

        for view_name, columns in PUBLIC_VIEW_COLUMNS.items():
            definitions = ", ".join(
                f'"{column}" {_sqlite_type(column)}' for column in columns
            )
            backing_table = f"_fixture_{view_name}"
            connection.execute(f'CREATE TABLE "{backing_table}" ({definitions})')
            selected = ", ".join(f'"{column}"' for column in columns)
            connection.execute(
                f'CREATE VIEW "{view_name}" AS '
                f'SELECT {selected} FROM "{backing_table}"'
            )

        connection.execute(
            """
            CREATE TABLE extraction_warnings (
                report_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL,
                code TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                context_json TEXT NOT NULL
            )
            """
        )

        reports = (
            _report_row(1, "2026-01-02", "SUCCESS", 1),
            _report_row(2, "2026-01-09", "SUCCESS_WITH_WARNINGS", 1),
            _report_row(3, "2026-01-16", "PARTIAL", 0),
            _report_row(4, "2026-01-23", "FAILED", 0),
        )
        for report in reports:
            _insert_view_row(connection, "v_reports", report)

        for report_id, report_date, status, eps in (
            (1, "2026-01-02", "SUCCESS", 100.0),
            (2, "2026-01-09", "SUCCESS_WITH_WARNINGS", 110.0),
            (3, "2026-01-16", "PARTIAL", 120.0),
            (4, "2026-01-23", "FAILED", 130.0),
        ):
            _insert_view_row(
                connection,
                "v_bottom_up_eps",
                {
                    "report_id": report_id,
                    "report_date": report_date,
                    "source_filename": f"fixture-{report_id}.pdf",
                    "status": status,
                    "period": "CY2026",
                    "period_type": "calendar_year",
                    "calendar_year": 2026,
                    "calendar_quarter": None,
                    "eps": eps,
                    "confidence": "HIGH",
                },
            )

        for sector, near_spread, far_spread, classification in (
            ("Energy", 4.0, -2.0, "FADING_LEADER"),
            ("Information Technology", 8.0, 12.0, "PERSISTENT_LEADER"),
        ):
            _insert_view_row(
                connection,
                "v_sector_leadership",
                {
                    "report_id": 2,
                    "report_date": "2026-01-09",
                    "source_filename": "fixture-2.pdf",
                    "status": "SUCCESS_WITH_WARNINGS",
                    "sector": sector,
                    "near_year_period": "CY2026",
                    "far_year_period": "CY2027",
                    "horizon_roll_flag": 0,
                    "near_relative_growth_spread_pp": near_spread,
                    "far_relative_growth_spread_pp": far_spread,
                    "relative_growth_transition_pp": far_spread - near_spread,
                    "classification": classification,
                    "data_quality": "COMPLETE",
                    "calculation_version": "fixture",
                },
            )

        _insert_view_row(
            connection,
            "v_sector_leadership",
            {
                "report_id": 3,
                "report_date": "2026-01-16",
                "source_filename": "fixture-3.pdf",
                "status": "PARTIAL",
                "sector": "Energy",
                "near_year_period": "CY2026",
                "far_year_period": "CY2027",
                "horizon_roll_flag": 0,
                "near_relative_growth_spread_pp": 5.0,
                "far_relative_growth_spread_pp": -1.0,
                "relative_growth_transition_pp": -6.0,
                "classification": "FADING_LEADER",
                "data_quality": "COMPLETE",
                "calculation_version": "fixture",
            },
        )

        for view_name, metric_columns in (
            (
                "v_period_growth",
                {"earnings_growth_pct": 10.0, "revenue_growth_pct": 6.0},
            ),
            (
                "v_sector_growth",
                {
                    "sector": "Information Technology",
                    "earnings_growth_pct": 18.0,
                    "revenue_growth_pct": 9.0,
                },
            ),
        ):
            for report_id, report_date, status in (
                (2, "2026-01-09", "SUCCESS_WITH_WARNINGS"),
                (3, "2026-01-16", "PARTIAL"),
                (4, "2026-01-23", "FAILED"),
            ):
                _insert_view_row(
                    connection,
                    view_name,
                    {
                        "report_id": report_id,
                        "report_date": report_date,
                        "source_filename": f"fixture-{report_id}.pdf",
                        "status": status,
                        "period": "CY2026",
                        "period_type": "calendar_year",
                        "estimate_status": "ESTIMATED",
                        **metric_columns,
                        "observation_as_of_date": report_date,
                        "anchor_date": report_date,
                    },
                )

        for report_id, report_date, status in (
            (2, "2026-01-09", "SUCCESS_WITH_WARNINGS"),
            (3, "2026-01-16", "PARTIAL"),
            (4, "2026-01-23", "FAILED"),
        ):
            _insert_view_row(
                connection,
                "v_guidance",
                {
                    "report_id": report_id,
                    "report_date": report_date,
                    "source_filename": f"fixture-{report_id}.pdf",
                    "status": status,
                    "period": "Q1 2026",
                    "period_type": "quarter",
                    "scope": "INDEX",
                    "sector": None,
                    "positive_count": 20,
                    "negative_count": 40,
                    "positive_pct": 33.3333,
                    "negative_pct": 66.6667,
                    "historical_5y_negative_guidance_avg_pct": 58.0,
                    "historical_10y_negative_guidance_avg_pct": 56.0,
                    "observation_as_of_date": report_date,
                    "anchor_date": report_date,
                },
            )

        connection.executemany(
            "INSERT INTO extraction_warnings VALUES (?, ?, ?, ?, ?, ?)",
            (
                (2, 1, "SAFE_WARNING", "WARNING", "fixture", "{}"),
                (3, 1, "PARTIAL_WARNING", "WARNING", "fixture", "{}"),
                (4, 1, "FAILED_WARNING", "ERROR", "fixture", "{}"),
            ),
        )
        connection.commit()
    return database


@pytest.fixture(scope="session")
def real_phase2_db() -> Path:
    database = default_database_path()
    if not database.is_file():
        pytest.skip(f"Real Phase 2 database is unavailable: {database}")
    return database
