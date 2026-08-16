# FactSet S&P 500 Earnings Momentum Dashboard

Phase 3 turns the canonical Phase 2 SQLite database into a local, interactive research application. It emphasizes transparent earnings fundamentals in this order: EPS revisions, forward EPS and earnings growth, margin, revenue growth, valuation, guidance, earnings surprises, and analyst targets.

The dashboard is a research interface, not a trading system. It does not produce buy/sell signals, portfolio allocations, or a composite 0–100 score.

The Market Regime page includes a user-controlled **Valuation Scenario Range** for the current two calendar-year EPS periods. It multiplies canonical bottom-up EPS by editable low/base/high P/E assumptions. Defaults come from the selected report's ten-year average, five-year average, and current forward P/E, sorted low to high. The result is illustrative scenario analysis—not a statistical forecast or FactSet target price.

Market Regime also shows the latest available S&P 500 index level from Yahoo Finance (`^GSPC`). The card includes the provider timestamp and prior-close change, while the valuation chart uses the quote only as a labeled reference line. This external overlay is cached for five minutes, may be delayed or unavailable, and is never written into the canonical FactSet database.

## Prerequisites

- Python 3.11 or newer
- The Phase 2 database at the default sibling location:
  `../factset_earnings/factset_earnings.sqlite`

The application opens the database read-only. By default it includes only reports where `v_reports.phase3_report_safe = 1`; the optional **Include partial reports** control is off initially.

## Install and launch on Windows

From this project directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If the database is not in the default sibling location, set its path before launch rather than copying or modifying the production database:

```powershell
$env:FACTSET_EARNINGS_DB_PATH = "C:\path\to\factset_earnings.sqlite"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run the tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Install and launch on macOS or Linux

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m streamlit run app.py
```

For a non-default database location:

```bash
export FACTSET_EARNINGS_DB_PATH=/path/to/factset_earnings.sqlite
python -m streamlit run app.py
```

Run the tests with:

```bash
python -m pytest
```

## Dashboard pages and data sources

| Page | Research question | Primary SQLite sources |
| --- | --- | --- |
| Market Regime | Is aggregate S&P 500 earnings momentum strengthening or weakening, and where is SPX currently trading? | `v_reports`, `v_bottom_up_eps`, `v_index_metrics`; Yahoo Finance `^GSPC` overlay |
| Sector Leadership | Which sectors lead or lag in the near and far forecast horizons? | `v_sector_leadership` |
| Sector Trends | How do sector earnings and revenue growth compare with the S&P 500 for the same period? | `v_sector_growth`, `v_period_growth`, `v_index_metrics` |
| Sector Quality & Valuation | Which sectors combine margin quality, forward growth, and reasonable valuation? | `v_sector_margin`, `v_sector_valuation`, `v_sector_leadership` |
| Guidance & Earnings Quality | Are management guidance and reported surprises confirming expectations? | `v_guidance`, `v_surprises` |
| Revision Movers | Which companies are the largest reported EPS revision movers? | `v_eps_revisions` |
| Analyst Sentiment | What do targets and rating distributions imply? | `v_target_prices`, `v_sector_target_prices` |
| Data Quality & Provenance | Which observations are safe, warned, partial, or traceable to source evidence? | `v_reports`, `extraction_warnings`, `v_observation_provenance` |

`v_eps_revisions` contains FactSet's Top-10 S&P 500 company movers, not full-market revision breadth. Aggregate EPS momentum therefore comes from calendar-year estimates in `v_bottom_up_eps`.

## Research safeguards

- Missing observations remain missing; the UI does not silently interpolate or forward-fill them.
- Growth comparisons match both report date and forecast period.
- Four-week and thirteen-week momentum use calendar dates, not row offsets.
- Leadership charts mark forecast-horizon changes from `horizon_roll_flag` and do not connect incompatible regimes.
- Percent changes and percentage-point changes are labeled separately.
- Valuation scenario levels expose both their EPS inputs and user-editable P/E assumptions; they are never labeled as forecasts or recommendations.
- Yahoo Finance pricing remains source-labeled, timestamped, fail-soft, and separate from the canonical SQLite snapshot.
- Source evidence remains accessible through the Data Quality & Provenance page.

See [PHASE3_DASHBOARD_CONTRACT.md](PHASE3_DASHBOARD_CONTRACT.md) for the complete behavioral and data contract.
