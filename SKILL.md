---
name: factset-earnings-momentum-dashboard
description: Operate, validate, test, or extend the local FactSet S&P 500 Earnings Momentum Dashboard over the canonical Phase 2 SQLite database. Use for launching the Streamlit research UI, auditing its report/view coverage, troubleshooting Phase 3 data behavior, or adding dashboard analytics and pages while preserving read-only access, safe-report defaults, date-aware EPS momentum, horizon-roll boundaries, missing-data gaps, and observation provenance.
---

# FactSet Earnings Momentum Dashboard

## Work from the contract

Read `PHASE3_DASHBOARD_CONTRACT.md` before changing calculations, filters, pages, or units. Read `PHASE3_VALIDATION.md` when the task concerns current database coverage, missingness, extraction warnings, or unsupported visuals.

Treat the sibling `../factset_earnings/factset_earnings.sqlite` as canonical input. On this workstation, that database resolves to `C:\Users\Tim\Documents\Codex\factset_sp500_earning_insight_tracker\factset_earnings\factset_earnings.sqlite`. Never mutate it, rewrite Phase 2 extraction, or modify raw PDFs. Use `FACTSET_EARNINGS_DB_PATH` only when an alternate database is explicitly needed.

## Operate the dashboard

From this directory, create/install the local environment if needed, then launch:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Use `scripts/validate_database.py` for a standard-library, read-only audit. Run `.\.venv\Scripts\python.exe -m pytest` after analytics, query, or filter changes.

## Preserve the architecture

- Put SQLite connection rules in `src/factset_dashboard/db.py`.
- Put explicit canonical-view reads in `src/factset_dashboard/queries.py`.
- Put reusable calculations in `src/factset_dashboard/metrics.py`.
- Put chart-ready joins and reshaping in `src/factset_dashboard/models.py`.
- Keep Plotly presentation in `src/factset_dashboard/charts.py` and Streamlit composition under `src/factset_dashboard/pages/`.
- Keep normal research queries safe-only unless the user enables partial reports. Let the audit page show every report status.
- Preserve SQL NULL and absent observations as `N/A` or visible gaps. Never zero-fill or interpolate silently.
- Match sector/index growth by the same report and exact period. Use calendar dates—not row offsets—for 4W and 13W momentum.
- Split or visibly mark lines at `horizon_roll_flag`; never imply incompatible forecast years form one continuous series.
- Keep Top-10 company revision movers distinct from full-market revision breadth.
- Keep valuation scenario ranges mechanical and transparent: exact-date calendar-year bottom-up EPS × visible, positive, ordered P/E assumptions. Label them as illustrative scenarios, never forecasts, target prices, expected returns, or recommendations.
- Treat Yahoo Finance `^GSPC` as an optional, timestamped external overlay. Cache it briefly, disclose possible delays, fail to `N/A` without blocking FactSet research, and never persist it in the canonical SQLite database.

## Verify changes

Run, in order:

1. `.\.venv\Scripts\python.exe -m pytest`
2. `.\.venv\Scripts\python.exe scripts\validate_database.py`
3. A Streamlit AppTest pass for every page or an equivalent interactive smoke test
4. A live local launch and health check when UI/runtime files changed

Report data limitations rather than correcting canonical values inside Phase 3. If a genuine Phase 2 defect blocks the dashboard, document the evidence and request a Phase 2 fix separately.
