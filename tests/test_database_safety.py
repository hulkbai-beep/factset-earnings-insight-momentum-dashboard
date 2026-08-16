from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from factset_dashboard.db import (
    EXPECTED_USER_VERSION,
    connect_readonly,
    validate_database,
)
from factset_dashboard.metrics import latest_safe_report
from factset_dashboard.queries import load_dashboard_bundle, load_report_health, load_reports


def _fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def test_01_database_opens_successfully_and_validates(phase3_db: Path) -> None:
    contract = validate_database(
        phase3_db,
        expected_user_version=EXPECTED_USER_VERSION,
    )
    assert contract.path == phase3_db.resolve()
    assert contract.schema_version == "2.1.0"

    with connect_readonly(phase3_db) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM v_reports").fetchone()[0] == 4


def test_02_only_safe_reports_are_used_by_default(phase3_db: Path) -> None:
    bundle = load_dashboard_bundle(phase3_db)

    for name, frame in bundle.items():
        if frame.empty or "report_id" not in frame.columns:
            continue
        assert set(frame["report_id"]) <= {1, 2}, name
        if "status" in frame.columns:
            assert set(frame["status"]) <= {"SUCCESS", "SUCCESS_WITH_WARNINGS"}, name

    assert bundle["reports"]["report_id"].tolist() == [1, 2]
    assert bundle["bottom_up_eps"]["report_id"].tolist() == [1, 2]
    assert set(load_report_health(phase3_db)["report_id"]) == {1, 2, 3, 4}


def test_03_partial_reports_are_excluded_unless_requested(phase3_db: Path) -> None:
    default_reports = load_reports(phase3_db)
    reports_with_partial = load_reports(phase3_db, include_partial=True)

    assert 3 not in set(default_reports["report_id"])
    assert set(reports_with_partial["report_id"]) == {1, 2, 3}
    assert 4 not in set(reports_with_partial["report_id"])


def test_04_latest_safe_report_selection_ignores_newer_unsafe_rows(
    phase3_db: Path,
) -> None:
    reports_with_partial = load_reports(phase3_db, include_partial=True)
    latest = latest_safe_report(reports_with_partial)

    assert latest is not None
    assert latest["report_id"] == 2
    assert latest["report_date"] == pd.Timestamp("2026-01-09")


def test_15_real_database_is_never_mutated_by_dashboard_access(
    real_phase2_db: Path,
) -> None:
    before = _fingerprint(real_phase2_db)

    contract = validate_database(real_phase2_db)
    assert contract.path == real_phase2_db.resolve()
    with connect_readonly(real_phase2_db) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only"):
            connection.execute(
                "CREATE TABLE phase3_dashboard_mutation_probe(value INTEGER)"
            )
    assert not load_reports(real_phase2_db).empty

    assert _fingerprint(real_phase2_db) == before
