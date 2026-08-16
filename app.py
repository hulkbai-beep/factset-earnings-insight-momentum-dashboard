"""Streamlit entry point for the FactSet Earnings Momentum Dashboard."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factset_dashboard.app import main  # noqa: E402


main()
