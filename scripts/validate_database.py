#!/usr/bin/env python3
"""Read-only validation report for the Phase 3 earnings dashboard database.

This script intentionally uses only the Python standard library.  It reports
coverage and known limitations; it never repairs or writes source data.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_DB = (
    Path(__file__).resolve().parents[2]
    / "factset_earnings"
    / "factset_earnings.sqlite"
)

SOURCE_VIEWS = (
    "v_reports",
    "v_index_metrics",
    "v_bottom_up_eps",
    "v_period_growth",
    "v_sector_growth",
    "v_sector_leadership",
    "v_sector_margin",
    "v_sector_valuation",
    "v_guidance",
    "v_surprises",
    "v_eps_revisions",
    "v_target_prices",
    "v_sector_target_prices",
    "v_observation_provenance",
)

# Missingness is measured only across rows belonging to safe reports.  Some
# structural fields (for example calendar_quarter on annual EPS rows) are
# intentionally omitted because their NULL values do not mean missing data.
KEY_FIELDS = {
    "v_bottom_up_eps": ("eps", "confidence"),
    "v_index_metrics": (
        "forward_12m_pe",
        "forward_12m_pe_5y_avg",
        "forward_12m_pe_10y_avg",
        "reported_forward_12m_eps",
        "derived_forward_12m_eps",
        "current_quarter_earnings_growth_pct",
        "current_quarter_revenue_growth_pct",
        "next_quarter_earnings_growth_pct",
        "next_quarter_revenue_growth_pct",
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
    "v_period_growth": ("earnings_growth_pct", "revenue_growth_pct"),
    "v_sector_growth": ("earnings_growth_pct", "revenue_growth_pct"),
    "v_sector_leadership": (
        "near_relative_growth_spread_pp",
        "far_relative_growth_spread_pp",
        "relative_growth_transition_pp",
        "classification",
        "data_quality",
    ),
    "v_sector_margin": (
        "current_net_profit_margin_pct",
        "year_ago_net_profit_margin_pct",
        "five_year_avg_net_profit_margin_pct",
        "margin_yoy_change_pp",
        "margin_vs_5y_pp",
    ),
    "v_sector_valuation": (
        "forward_12m_pe",
        "five_year_avg_forward_pe",
        "ten_year_avg_forward_pe",
        "premium_to_5y_pct",
        "premium_to_10y_pct",
    ),
    "v_guidance": (
        "positive_count",
        "negative_count",
        "positive_pct",
        "negative_pct",
        "historical_5y_negative_guidance_avg_pct",
        "historical_10y_negative_guidance_avg_pct",
    ),
    "v_surprises": (
        "positive_eps_surprise_pct",
        "positive_revenue_surprise_pct",
        "eps_surprise_magnitude_pct",
        "revenue_surprise_magnitude_pct",
    ),
    "v_eps_revisions": ("company", "revision_pct", "rank"),
    "v_target_prices": (
        "bottom_up_target_price",
        "implied_upside_pct",
        "buy_rating_pct",
        "hold_rating_pct",
        "sell_rating_pct",
        "buy_rating_count",
        "hold_rating_count",
        "sell_rating_count",
    ),
    "v_sector_target_prices": ("sector", "implied_upside_pct"),
    "v_observation_provenance": (
        "source_page",
        "section_title",
        "chart_title",
        "raw_text",
        "raw_label",
        "extraction_method",
        "confidence",
    ),
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a read-only Markdown validation report for Phase 3."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    return parser.parse_args(argv)


def open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite database not found: {resolved}")
    connection = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def object_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        )
    }


def columns(connection: sqlite3.Connection, name: str) -> set[str]:
    # Object names originate from sqlite_master or constants above, never from
    # untrusted database values.
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')}


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        values = []
        for value in row:
            text = "N/A" if value is None else str(value)
            values.append(text.replace("|", "\\|"))
        print("| " + " | ".join(values) + " |")


def pct(numerator: int, denominator: int) -> str:
    return "N/A" if denominator == 0 else f"{100.0 * numerator / denominator:.1f}%"


def safe_filter_sql(view: str) -> str:
    return f'FROM "{view}" x JOIN v_reports r USING(report_id) WHERE r.phase3_report_safe = 1'


def missing_safe_dates(connection: sqlite3.Connection, view: str) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            f'''SELECT r.report_date
                FROM v_reports r
                LEFT JOIN "{view}" x USING(report_id)
                WHERE r.phase3_report_safe = 1 AND x.report_id IS NULL
                ORDER BY r.report_date'''
        )
    ]


def scalar(connection: sqlite3.Connection, sql: str, parameters: tuple = ()):
    row = connection.execute(sql, parameters).fetchone()
    return None if row is None else row[0]


def print_inventory(connection: sqlite3.Connection) -> None:
    summary = connection.execute(
        """SELECT COUNT(*) AS total,
                  SUM(phase3_report_safe = 1) AS safe,
                  SUM(status = 'PARTIAL') AS partial,
                  MIN(report_date) AS earliest,
                  MAX(report_date) AS latest,
                  MAX(CASE WHEN phase3_report_safe = 1 THEN report_date END) AS latest_safe
           FROM v_reports"""
    ).fetchone()
    print("## Report inventory")
    print()
    markdown_table(
        ("Reports", "Safe", "Partial", "Earliest", "Latest", "Latest safe"),
        [tuple(summary)],
    )
    print()
    status_rows = connection.execute(
        """SELECT status, phase3_report_safe, COUNT(*)
           FROM v_reports GROUP BY status, phase3_report_safe ORDER BY status"""
    ).fetchall()
    markdown_table(("Status", "Phase 3 safe", "Reports"), status_rows)
    print()
    print(
        "Safety rule: `phase3_report_safe = 1` only when status is "
        "`SUCCESS` or `SUCCESS_WITH_WARNINGS`; normal dashboard queries must "
        "exclude all other statuses."
    )
    print()


def print_sectors(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """SELECT DISTINCT s.sector
           FROM v_sector_growth s JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1
           ORDER BY s.sector"""
    ).fetchall()
    print("## Available sectors")
    print()
    print(f"{len(rows)} sectors: " + ", ".join(row[0] for row in rows) + ".")
    print()


def print_view_coverage(connection: sqlite3.Connection, names: set[str]) -> None:
    report_rows = []
    for view in SOURCE_VIEWS:
        if view not in names:
            report_rows.append((view, "MISSING", None, None, None, None, None))
            continue
        if view == "v_reports":
            row = connection.execute(
                """SELECT COUNT(*), SUM(phase3_report_safe = 1), COUNT(*),
                          SUM(phase3_report_safe = 1),
                          MIN(CASE WHEN phase3_report_safe = 1 THEN report_date END),
                          MAX(CASE WHEN phase3_report_safe = 1 THEN report_date END)
                   FROM v_reports"""
            ).fetchone()
            missing = []
        else:
            row = connection.execute(
                f'''SELECT COUNT(*),
                           SUM(CASE WHEN r.phase3_report_safe = 1 THEN 1 ELSE 0 END),
                           COUNT(DISTINCT x.report_id),
                           COUNT(DISTINCT CASE WHEN r.phase3_report_safe = 1 THEN x.report_id END),
                           MIN(CASE WHEN r.phase3_report_safe = 1 THEN x.report_date END),
                           MAX(CASE WHEN r.phase3_report_safe = 1 THEN x.report_date END)
                    FROM "{view}" x JOIN v_reports r USING(report_id)'''
            ).fetchone()
            missing = missing_safe_dates(connection, view)
        report_rows.append(
            (
                view,
                row[0],
                row[1],
                row[2],
                row[3],
                f"{row[4]} to {row[5]}" if row[4] else "N/A",
                ", ".join(missing) if missing else "None",
            )
        )
    print("## Source-view coverage")
    print()
    markdown_table(
        (
            "View",
            "All rows",
            "Safe rows",
            "All reports",
            "Safe reports",
            "Safe date span",
            "Missing safe report dates",
        ),
        report_rows,
    )
    print()


def print_core_eps_coverage(connection: sqlite3.Connection) -> None:
    latest = connection.execute(
        """SELECT near_year_period, far_year_period
           FROM v_index_metrics i JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1
           ORDER BY i.report_date DESC LIMIT 1"""
    ).fetchone()
    periods = [value for value in latest if value]
    rows = []
    for period in periods:
        row = connection.execute(
            """SELECT COUNT(*), SUM(b.eps IS NULL), MIN(b.report_date), MAX(b.report_date)
               FROM v_bottom_up_eps b JOIN v_reports r USING(report_id)
               WHERE r.phase3_report_safe = 1 AND b.period = ?""",
            (period,),
        ).fetchone()
        rows.append((period, row[0], row[1], pct(row[1], row[0]), row[2], row[3]))
    print("## Current calendar-year EPS coverage")
    print()
    markdown_table(
        ("Period", "Safe observations", "Missing EPS", "Missing rate", "First", "Last"),
        rows,
    )
    print()


def print_missingness(
    connection: sqlite3.Connection, names: set[str]
) -> None:
    output = []
    for view, fields in KEY_FIELDS.items():
        if view not in names:
            for field in fields:
                output.append((view, field, "VIEW MISSING", None, None))
            continue
        available_columns = columns(connection, view)
        denominator = scalar(
            connection, f'SELECT COUNT(*) {safe_filter_sql(view)}'
        )
        for field in fields:
            if field not in available_columns:
                output.append((view, field, denominator, "FIELD MISSING", None))
                continue
            nulls = scalar(
                connection,
                f'SELECT COUNT(*) {safe_filter_sql(view)} AND x."{field}" IS NULL',
            )
            output.append((view, field, denominator, nulls, pct(nulls, denominator)))
    print("## Key-field missingness (safe reports only)")
    print()
    markdown_table(("View", "Field", "Rows", "NULL", "Missing rate"), output)
    print()


def print_horizon_rolls(connection: sqlite3.Connection) -> None:
    rolls = connection.execute(
        """SELECT l.report_date, l.near_year_period, l.far_year_period,
                  COUNT(*) AS sector_rows
           FROM v_sector_leadership l JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1 AND horizon_roll_flag = 1
           GROUP BY l.report_id, l.report_date, l.near_year_period, l.far_year_period
           ORDER BY l.report_date"""
    ).fetchall()
    null_classifications = connection.execute(
        """SELECT COUNT(*)
           FROM v_sector_leadership l JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1 AND classification IS NULL"""
    ).fetchone()[0]
    missing = missing_safe_dates(connection, "v_sector_leadership")
    print("## Leadership horizons")
    print()
    if rolls:
        markdown_table(
            ("Roll date", "Near period after roll", "Far period after roll", "Sector rows"),
            rolls,
        )
    else:
        print("No horizon roll was detected.")
    print()
    print(
        f"Leadership is absent on {len(missing)} safe report(s): "
        f"{', '.join(missing) if missing else 'none'}."
    )
    print(
        f"Safe leadership rows with no classification: {null_classifications}. "
        "Do not connect or classify these missing observations."
    )
    print()


def print_guidance_detail(connection: sqlite3.Connection) -> None:
    sector = connection.execute(
        """SELECT COUNT(*) AS rows,
                  SUM(positive_count IS NOT NULL AND negative_count IS NOT NULL) AS paired
           FROM v_guidance g JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1 AND UPPER(g.scope) = 'SECTOR'"""
    ).fetchone()
    index_rows = connection.execute(
        """SELECT period_type, COUNT(*) AS rows, COUNT(DISTINCT g.report_id) AS reports,
                  SUM(positive_count IS NULL OR negative_count IS NULL) AS incomplete_counts,
                  SUM(historical_5y_negative_guidance_avg_pct IS NULL) AS missing_5y,
                  SUM(historical_10y_negative_guidance_avg_pct IS NULL) AS missing_10y
           FROM v_guidance g JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1 AND UPPER(g.scope) = 'INDEX'
           GROUP BY period_type ORDER BY period_type"""
    ).fetchall()
    print("## Guidance usability")
    print()
    print(
        f"Sector guidance rows with both positive and negative counts: "
        f"{sector['paired']}/{sector['rows']} ({pct(sector['paired'], sector['rows'])})."
    )
    print()
    markdown_table(
        (
            "Index period type",
            "Rows",
            "Reports",
            "Incomplete counts",
            "Missing 5Y average",
            "Missing 10Y average",
        ),
        index_rows,
    )
    print()


def print_warnings(connection: sqlite3.Connection) -> None:
    total = scalar(connection, "SELECT COUNT(*) FROM extraction_warnings")
    print("## Extraction warnings")
    print()
    print(f"Total warnings: {total}.")
    print()
    severity = connection.execute(
        """SELECT severity, COUNT(*) AS warnings, COUNT(DISTINCT report_id) AS reports
           FROM extraction_warnings GROUP BY severity ORDER BY warnings DESC"""
    ).fetchall()
    markdown_table(("Severity", "Warnings", "Reports"), severity)
    print()
    codes = connection.execute(
        """SELECT code, severity, COUNT(*) AS warnings,
                  COUNT(DISTINCT report_id) AS reports
           FROM extraction_warnings
           GROUP BY code, severity ORDER BY warnings DESC, code"""
    ).fetchall()
    markdown_table(("Code", "Severity", "Warnings", "Reports"), codes)
    print()


def print_anomaly_check(connection: sqlite3.Connection) -> None:
    target_date = "2026-06-05"
    index_value = scalar(
        connection,
        """SELECT near_year_earnings_growth_pct
           FROM v_index_metrics
           WHERE report_date = ? AND near_year_period = 'CY2026'""",
        (target_date,),
    )
    period_value = scalar(
        connection,
        """SELECT earnings_growth_pct
           FROM v_period_growth
           WHERE report_date = ? AND period = 'CY2026'""",
        (target_date,),
    )
    raw_texts = [
        row[0]
        for row in connection.execute(
            """SELECT DISTINCT raw_text
               FROM v_observation_provenance
               WHERE report_date = ?
                 AND raw_text IS NOT NULL
                 AND ((table_name = 'index_metrics'
                       AND field_name = 'current_calendar_year_earnings_growth_pct')
                      OR
                      (table_name = 'period_growth'
                       AND field_name = 'earnings_growth_pct'
                       AND observation_key LIKE '%"period":"CY2026"%'))""",
            (target_date,),
        )
    ]
    narrative_values = []
    for text in raw_texts:
        match = re.search(
            r"earnings growth of\s+([-+]?\d+(?:\.\d+)?)%", text, re.IGNORECASE
        )
        if match:
            narrative_values.append(float(match.group(1)))
    narrative_values = sorted(set(narrative_values))
    canonical_values = [value for value in (index_value, period_value) if value is not None]
    detected = bool(
        canonical_values
        and narrative_values
        and min(canonical_values) < 5.0
        and max(narrative_values) - min(canonical_values) >= 10.0
    )
    print("## Canonical growth anomaly check")
    print()
    print(f"Status: **{'DETECTED' if detected else 'not detected'}**")
    print()
    markdown_table(
        ("Date", "Period", "Index canonical", "Period-growth canonical", "Narrative evidence"),
        [
            (
                target_date,
                "CY2026",
                index_value,
                period_value,
                ", ".join(f"{value:g}%" for value in narrative_values) or "None",
            )
        ],
    )
    print()
    if detected:
        print(
            "The database stores 2.2% while provenance contains a 22.8% "
            "narrative observation. This validator only flags the discrepancy; "
            "it does not correct or overwrite either value."
        )
    else:
        print(
            "The known 2026-06-05 discrepancy was not reproduced. Review the "
            "database version and provenance before relying on that point."
        )
    print()


def print_visual_support(connection: sqlite3.Connection) -> None:
    safe_index_rows = scalar(
        connection,
        """SELECT COUNT(*) FROM v_index_metrics i JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1""",
    )
    forward_eps_known = scalar(
        connection,
        """SELECT COUNT(*) FROM v_index_metrics i JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1
             AND (reported_forward_12m_eps IS NOT NULL OR derived_forward_12m_eps IS NOT NULL)""",
    )
    sector_margin_rows = scalar(
        connection,
        """SELECT COUNT(*) FROM v_sector_margin m JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1""",
    )
    sector_margin_5y_known = scalar(
        connection,
        """SELECT COUNT(*) FROM v_sector_margin m JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1
             AND five_year_avg_net_profit_margin_pct IS NOT NULL""",
    )
    target_rows = scalar(
        connection,
        """SELECT COUNT(*) FROM v_target_prices t JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1""",
    )
    target_count_rows = scalar(
        connection,
        """SELECT COUNT(*) FROM v_target_prices t JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1
             AND buy_rating_count IS NOT NULL
             AND hold_rating_count IS NOT NULL
             AND sell_rating_count IS NOT NULL""",
    )
    guidance = connection.execute(
        """SELECT COUNT(*) AS rows,
                  SUM(positive_count IS NOT NULL AND negative_count IS NOT NULL) AS paired
           FROM v_guidance g JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1 AND UPPER(scope) = 'SECTOR'"""
    ).fetchone()
    surprise = connection.execute(
        """SELECT COUNT(*) AS rows,
                  SUM(positive_eps_surprise_pct IS NOT NULL
                      AND positive_revenue_surprise_pct IS NOT NULL
                      AND eps_surprise_magnitude_pct IS NOT NULL
                      AND revenue_surprise_magnitude_pct IS NOT NULL) AS complete
           FROM v_surprises s JOIN v_reports r USING(report_id)
           WHERE r.phase3_report_safe = 1"""
    ).fetchone()
    revision_scope = scalar(
        connection,
        "SELECT group_concat(DISTINCT chart_scope) FROM v_eps_revisions",
    )
    leadership_missing = missing_safe_dates(connection, "v_sector_leadership")

    print("## Visualization support and limitations")
    print()
    bullets = [
        (
            "Unsupported",
            f"Forward-12M EPS series: {forward_eps_known}/{safe_index_rows} safe rows have "
            "reported or derived EPS. Use calendar-year bottom-up EPS instead.",
        ),
        (
            "Unsupported" if sector_margin_5y_known == 0 else "Limited",
            f"Sector five-year margin comparison: {sector_margin_5y_known}/{sector_margin_rows} "
            "safe sector rows are populated.",
        ),
        (
            "Unsupported" if target_count_rows == 0 else "Limited",
            f"Analyst rating-count chart: {target_count_rows}/{target_rows} safe report rows "
            "contain all three counts; rating percentages remain the usable fields.",
        ),
        (
            "Limited",
            f"Sector guidance ratios/heatmap: {guidance['paired']}/{guidance['rows']} rows "
            "have both required counts. Missing counts are not zero.",
        ),
        (
            "Limited",
            f"Surprise trend: {surprise['complete']}/{surprise['rows']} safe reports have all "
            "four primary surprise fields.",
        ),
        (
            "Limited",
            "Leadership history has missing safe report dates "
            f"({', '.join(leadership_missing) if leadership_missing else 'none'}) and must "
            "also be segmented at horizon rolls.",
        ),
        (
            "Unsupported",
            f"Market-wide revision breadth: `v_eps_revisions.chart_scope` is "
            f"`{revision_scope}` (Top-10 movers only).",
        ),
    ]
    for label, description in bullets:
        print(f"- **{label}:** {description}")
    print()


def validate_required_objects(names: set[str]) -> list[str]:
    required = set(SOURCE_VIEWS) | {"extraction_warnings"}
    return sorted(required - names)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = args.db.expanduser().resolve()
    try:
        connection = open_read_only(db_path)
    except (FileNotFoundError, sqlite3.Error) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 2

    try:
        names = object_names(connection)
        missing_objects = validate_required_objects(names)
        print("# Phase 3 Database Validation")
        print()
        print(f"Database: `{db_path}`")
        print()
        print("Connection mode: SQLite URI `mode=ro` with `query_only=ON`.")
        print()
        if missing_objects:
            print("## Contract failure")
            print()
            print("Missing required objects: " + ", ".join(missing_objects))
            return 1

        print_inventory(connection)
        print_sectors(connection)
        print_view_coverage(connection, names)
        print_core_eps_coverage(connection)
        print_missingness(connection, names)
        print_horizon_rolls(connection)
        print_guidance_detail(connection)
        print_warnings(connection)
        print_anomaly_check(connection)
        print_visual_support(connection)
        print("## Validation conclusion")
        print()
        print(
            "The database contract is queryable for Phase 3. Dashboard queries "
            "must retain NULL gaps, exclude unsafe reports by default, mark horizon "
            "rolls, and disclose the limitations above."
        )
        return 0
    except sqlite3.Error as exc:
        print(f"Validation query failed: {exc}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
