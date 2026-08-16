"""Read-only SQLite access and Phase 2 contract validation."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import quote


DatabasePath = str | os.PathLike[str]
DATABASE_ENV_VAR: Final = "FACTSET_EARNINGS_DB_PATH"
EXPECTED_USER_VERSION: Final = 20100

REQUIRED_VIEWS: Final[frozenset[str]] = frozenset(
    {
        "v_reports",
        "v_index_metrics",
        "v_bottom_up_eps",
        "v_period_growth",
        "v_sector_growth",
        "v_sector_leadership",
        "v_sector_margin",
        "v_sector_valuation",
        "v_eps_revisions",
        "v_guidance",
        "v_surprises",
        "v_target_prices",
        "v_sector_target_prices",
        "v_observation_provenance",
    }
)


class DatabaseValidationError(RuntimeError):
    """Raised when a SQLite file does not implement the Phase 2 contract."""


@dataclass(frozen=True, slots=True)
class DatabaseContract:
    """Validated metadata for a Phase 2 database."""

    path: Path
    user_version: int
    schema_version: str | None
    available_views: frozenset[str]


def default_database_path() -> Path:
    """Return the configured database path or the workspace sibling default."""

    configured = os.getenv(DATABASE_ENV_VAR)
    if configured:
        return Path(configured).expanduser().resolve()

    # package/src/project/workspace, then the Phase 1/2 data directory
    workspace_root = Path(__file__).resolve().parents[3]
    return (workspace_root / "factset_earnings" / "factset_earnings.sqlite").resolve()


def _database_uri(path: Path) -> str:
    encoded_path = quote(path.as_posix(), safe="/:")
    return f"file:{encoded_path}?mode=ro"


def connect_readonly(
    db_path: DatabasePath | None = None,
    *,
    validate: bool = True,
) -> sqlite3.Connection:
    """Open SQLite in OS-enforced read-only mode and enable query-only mode."""

    path = Path(db_path).expanduser().resolve() if db_path is not None else default_database_path()
    if not path.is_file():
        raise FileNotFoundError(f"FactSet SQLite database not found: {path}")

    connection = sqlite3.connect(_database_uri(path), uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        if int(connection.execute("PRAGMA query_only").fetchone()[0]) != 1:
            raise DatabaseValidationError("SQLite query_only mode could not be enabled")
        if validate:
            validate_database(connection)
    except Exception:
        connection.close()
        raise
    return connection


def validate_database(
    database: DatabasePath | sqlite3.Connection | None = None,
    *,
    required_views: frozenset[str] = REQUIRED_VIEWS,
    expected_user_version: int | None = None,
) -> DatabaseContract:
    """Validate required public views and return database contract metadata.

    ``expected_user_version`` is opt-in so additive future schema versions can be
    inspected while the stable public-view contract remains compatible.
    """

    owns_connection = not isinstance(database, sqlite3.Connection)
    if owns_connection:
        connection = connect_readonly(database, validate=False)
    else:
        connection = database

    try:
        database_row = connection.execute("PRAGMA database_list").fetchone()
        path_text = database_row[2] if database_row and len(database_row) > 2 else ""
        path = Path(path_text).resolve() if path_text else default_database_path()
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        views = frozenset(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'view'"
            ).fetchall()
        )
        missing = sorted(required_views - views)
        if missing:
            raise DatabaseValidationError(
                "Database is missing required Phase 2 views: " + ", ".join(missing)
            )
        if expected_user_version is not None and user_version != expected_user_version:
            raise DatabaseValidationError(
                f"Database user_version={user_version}; expected {expected_user_version}"
            )

        schema_version: str | None = None
        has_metadata = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_metadata'"
        ).fetchone()
        if has_metadata:
            row = connection.execute(
                "SELECT value FROM schema_metadata WHERE key='schema_version'"
            ).fetchone()
            schema_version = str(row[0]) if row else None

        return DatabaseContract(
            path=path,
            user_version=user_version,
            schema_version=schema_version,
            available_views=views,
        )
    finally:
        if owns_connection:
            connection.close()
