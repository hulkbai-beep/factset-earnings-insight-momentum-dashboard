# Phase 3 Dashboard Contract

## 1. Purpose and scope

The FactSet S&P 500 Earnings Momentum Dashboard is a local, read-only research interface over the canonical Phase 2 SQLite database. It makes aggregate estimate momentum, sector leadership, fundamental quality, valuation, earnings confirmation, and source provenance visible without re-running PDF extraction.

Research priority is:

1. EPS revisions
2. Forward EPS and earnings growth
3. Margin
4. Revenue growth
5. Valuation
6. Guidance
7. Earnings surprises
8. Analyst targets

Phase 3 does not create trading recommendations, allocations, buy/sell signals, or an arbitrary composite score. Phase 2 views are the primary read interface; extraction logic does not belong in the dashboard.

## 2. Architecture and database safety

The application separates responsibilities:

```text
Phase 2 SQLite views
        ↓
Read-only repository and query layer
        ↓
Derived metrics layer
        ↓
Chart-ready data models
        ↓
Streamlit pages
```

The production database connection must use SQLite URI read-only mode (`mode=ro`) wherever practical and enable `PRAGMA query_only = ON`. Dashboard code must not run migrations, create schema objects, update data, or invoke the Phase 2 write-oriented `SnapshotStorage` connection. Database resolution uses the sibling `../factset_earnings/factset_earnings.sqlite` by default and accepts `FACTSET_EARNINGS_DB_PATH` as the explicit environment override.

The default report universe is the set of rows from `v_reports` where `phase3_report_safe = 1`. This includes successful reports and successful reports with warnings. `PARTIAL` reports are excluded by default. The **Include partial reports** control may add `PARTIAL` rows explicitly; it is off initially. `FAILED` reports are never included in research charts.

All downstream queries must apply the selected report universe consistently. The latest safe report is the default selected date. Date-range, report-date, sector, and forecast-period filters must not manufacture observations outside the filtered universe.

## 3. Page contracts

### Page 1 — Market Regime

Primary sources: `v_reports`, `v_bottom_up_eps`, `v_index_metrics`. Optional external overlay: Yahoo Finance `^GSPC`.

The landing page answers whether S&P 500 earnings momentum is strengthening or weakening. It presents:

- latest included FactSet report date;
- the latest available SPX index level from Yahoo Finance, with source, timestamp, currency, prior-close change, and a selected-report FactSet price reference where available;
- dynamically selected near- and far-calendar-year bottom-up EPS with 1P, 4W, and 13W changes;
- near-year, far-year, current-quarter, and next-quarter earnings growth;
- the corresponding revenue growth outlook;
- current and year-ago net profit margins and their percentage-point difference;
- forward 12-month P/E, five-year average P/E, ten-year average P/E, and premiums or discounts;
- a user-controlled low/base/high valuation scenario range for the selected near- and far-calendar-year EPS periods;
- time-series charts for calendar-year bottom-up EPS, earnings growth, revenue growth, margin, and valuation.

Calendar-year labels are determined from available data and never hardcoded. Null reported or derived forward-12-month EPS fields are not fabricated. Forecast growth lines are segmented or visibly marked at horizon rolls.

The valuation scenario is calculated as calendar-year bottom-up EPS multiplied by an explicit P/E assumption. Its default low/base/high assumptions are the selected report's current forward 12-month P/E, five-year average, and ten-year average sorted from low to high. Users may edit those assumptions, but they must remain positive and ordered. The output is labeled as an illustrative index-level scenario—not a statistical price prediction, FactSet target price, or investment recommendation. Missing EPS or valuation references remain missing.

The Yahoo Finance SPX quote is a noncanonical, informational market overlay. It must be labeled `^GSPC`, show its provider timestamp, disclose that it may be delayed, and fail without blocking canonical FactSet research. It is cached for no more than five minutes in process and is never inserted into SQLite. When present, the latest SPX level may be drawn as a labeled reference line on the valuation scenario chart. Historical FactSet observations and external current-market data must remain visibly distinct.

### Page 2 — Sector Leadership

Primary source: `v_sector_leadership`.

For a selected report date, the leadership quadrant plots `near_relative_growth_spread_pp` on the x-axis and `far_relative_growth_spread_pp` on the y-axis, with one observation per available sector. Zero reference lines define these analytical regimes:

- upper right: `PERSISTENT_LEADER`;
- upper left: `EMERGING_LEADER`;
- lower right: `FADING_LEADER`;
- lower left: `PERSISTENT_LAGGARD`.

Hover details include sector, near-year period, far-year period, classification, transition spread, and data quality. A sortable table exposes the same fields. A sector-by-report-date classification heatmap preserves missing cells and marks horizon-roll dates. Regime labels are descriptive, not investment recommendations.

### Page 3 — Sector Trends

Primary sources: `v_sector_growth`, `v_period_growth`, and, where appropriate, `v_index_metrics`.

Users select one or more sectors and a forecast period. Earnings and revenue growth trends compare each sector with the S&P 500 only when report date and period both match. Growth spread is:

```text
sector growth percent - S&P 500 growth percent
```

The result is expressed in percentage points. Missing sector or index observations remain missing. Periods with similar labels but different identities or estimate horizons must not be joined.

### Page 4 — Sector Quality & Valuation

Primary sources: `v_sector_margin`, `v_sector_valuation`, and `v_sector_leadership`.

At a selected report date, this page provides:

- margin-expansion ranking by canonical `margin_yoy_change_pp`;
- sector margin trends for current and year-ago margin;
- forward P/E and premium/discount rankings using canonical five- and ten-year fields;
- a growth-versus-valuation map with `premium_to_5y_pct` on the x-axis and `far_relative_growth_spread_pp` on the y-axis.

The opportunity-map quadrants describe combinations of relative growth and valuation. They are not buy/sell recommendations. Sector five-year average margins are not charted when the field has no usable coverage.

### Page 5 — Guidance & Earnings Quality

Primary sources: `v_guidance` and `v_surprises`.

The guidance section shows available positive and negative counts and percentages, together with historical negative-guidance averages where present. Sector rankings or heatmaps require the counts needed by the displayed calculation. A missing count is not zero, and a ratio is null when either required count is null or when its denominator is not economically meaningful.

The surprises section trends positive EPS surprise percent, positive revenue surprise percent, EPS surprise magnitude percent, and revenue surprise magnitude percent. These are confirmation indicators and remain visually secondary to forward estimate momentum.

### Page 6 — Revision Movers

Primary source: `v_eps_revisions`.

The page title is **Top S&P 500 EPS Revision Movers**. Separate upward and downward tables/charts show company, revision percent, rank, period, and revision window for the selected report date.

This view is an idea-generation and anomaly-discovery tool. The source is FactSet's Top-10 company mover set and must never be labeled or interpreted as full-market EPS revision breadth.

### Page 7 — Analyst Sentiment

Primary sources: `v_target_prices` and `v_sector_target_prices`.

The index section shows bottom-up target price, implied upside, and Buy/Hold/Sell percentages where available. The sector section ranks sectors by implied target upside. Titles and explanatory copy make clear that target-price data is secondary to earnings fundamentals.

### Page 8 — Data Quality & Provenance

Primary sources: `v_reports`, `extraction_warnings`, and `v_observation_provenance`.

Report Health lists report date, filename, extraction status, page count, and `phase3_report_safe`. Warning Summary groups or filters warnings by report date, warning code, and severity. Observation Provenance supports tracing available values to source filename, PDF page, section title, chart title, raw label, raw text, extraction method, and confidence.

The page exposes limitations rather than converting warnings or missing evidence into apparent certainty.

## 4. Derived metrics

### 4.1 Bottom-up EPS revisions

EPS revisions compare observations for the same calendar-year period:

```text
revision_pct = (current_eps / historical_eps - 1) × 100
```

The result is null if current EPS is null, historical EPS is null, historical EPS is zero, or no eligible comparison exists.

The supported windows are:

- **1P change:** compare with the immediately preceding included FactSet publication that contains a valid observation for the same calendar-year period. The label is 1P, not one week.
- **4W change:** set the target date to `current report date - 28 calendar days`. Choose the most recent valid observation on or before that target date for the same period.
- **13W change:** set the target date to `current report date - 91 calendar days`. Choose the most recent valid observation on or before that target date for the same period.

For 4W and 13W, the selected historical observation may be at most 14 calendar days older than the target date. Equivalently:

```text
0 <= target_date - matched_report_date <= 14 days
```

If no observation meets that rule, the comparison is null. Observations after the target date are never used. Row-offset logic such as `LAG(4)` or `LAG(13)` is prohibited because the FactSet publication schedule is irregular.

### 4.2 Margin expansion

Use canonical `margin_yoy_change_pp` when present. A fallback calculation may be used only when both components are available and must produce the same unit:

```text
current_net_profit_margin_pct - year_ago_net_profit_margin_pct
```

The result is percentage points, not percent change.

### 4.3 Valuation premium or discount

Use canonical `premium_to_5y_pct` and `premium_to_10y_pct` from the Phase 2 views. Do not duplicate those formulas in UI components. Index-level equivalents may be calculated in the analytics layer only when current and historical-average P/E inputs are both present and the denominator is nonzero.

### 4.4 Sector relative growth

Leadership classification and near/far relative growth come from `v_sector_leadership`. Sector-versus-index trend spreads may be calculated only after matching the same included report and exact forecast period. Missing sector or index observations produce a missing spread, not zero.

### 4.5 Guidance ratios

Use canonical percentages when available. A count-based percentage may be calculated only when both positive and negative counts are non-null and their sum is greater than zero. Otherwise it is null.

### 4.6 Index-level valuation scenarios

For each selected calendar-year period:

```text
illustrative index level = bottom-up EPS × selected P/E multiple
```

The low, base, and high outputs use independently visible P/E assumptions. Defaults are grounded in the selected report's current forward P/E and five- and ten-year averages, sorted low to high; the analytics layer does not invent fallback multiples. Calculations use EPS from the exact selected report date and period. They do not backfill a missing EPS value, assign probabilities, extrapolate prices, or incorporate dividends. Inputs must be finite, positive, and satisfy `low <= base <= high`.

## 5. Forecast-horizon rolls

The semantic meaning of near-year and far-year fields changes over time. `horizon_roll_flag` from `v_sector_leadership` is the canonical roll indicator.

At each roll:

- show a vertical marker or explicit annotation;
- display the old and new `(near_year_period, far_year_period)` regimes where practical;
- split near/far time-series lines into separate regime segments;
- never draw a continuous line that implies the old and new horizons are the same series;
- preserve missing observations around the transition.

Heatmaps may continue across the date axis only when roll dates are visibly marked and each cell retains its report-specific classification and period metadata.

## 6. Missing-data behavior

- SQL `NULL`, pandas `NA`/`NaN`, and absent observations are never converted to economic zero by default.
- No metric is silently interpolated, forward-filled, or backfilled.
- Line charts show gaps (`connectgaps = false` or equivalent).
- Tables and KPI cards render missing values as `N/A`.
- Derived calculations return missing when any required input is missing or invalid.
- A missing sector row does not become a zero-growth sector.
- Missing guidance counts do not become zero counts.
- Missing leadership inputs do not become laggard classifications.
- Filters do not synthesize rows for unavailable dates, sectors, or periods.
- Any future visualization that intentionally transforms missing data must label the transformation in the UI and document it here before release.

## 7. Units and display conventions

| Measure | Unit and display rule |
| --- | --- |
| Bottom-up EPS | US dollars per index share; label the calendar-year period |
| EPS revision | Percent change (`%`) |
| Earnings and revenue growth | Percent (`%`) |
| Sector-minus-index growth | Percentage points (`pp`) |
| Net profit margin | Percent (`%`) |
| Margin expansion | Percentage points (`pp`) |
| Forward P/E | Multiple (`x`) |
| Valuation premium/discount | Percent (`%`) |
| Guidance and surprise rates | Percent (`%`) |
| Guidance and rating totals | Counts |
| Target price and index level | Index points, not EPS dollars |
| Valuation scenario range | Illustrative S&P 500 index points with the EPS period and P/E multiple shown |
| Implied target upside | Percent (`%`) |

Titles, axes, hover text, and tables must distinguish percent changes from percentage-point differences.

## 8. Performance and caching

The database is small, but queries should select only required columns and respect active filters. Cache stable read results by database identity and query parameters where appropriate. Cache invalidation must account for database path and file modification state. Cached data must not weaken the safe-report filter or preserve stale filter selections across incompatible databases.

External Yahoo Finance market data uses a short, five-minute in-process cache. Network failure, throttling, malformed payloads, or missing timestamps must produce an `N/A` overlay without preventing the dashboard from loading.

## 9. Known limitations

- Available history is primarily 2026 year-to-date and is insufficient for robust multi-year rolling percentile normalization.
- Publication dates are irregular; 1P is not guaranteed to equal one week.
- `v_eps_revisions` contains only Top-10 company movers and is not market breadth.
- Reported and derived forward-12-month EPS fields may be null; calendar-year bottom-up EPS is the initial aggregate signal.
- Sector five-year average margin coverage may be absent or unusable.
- Guidance extraction contains ambiguity warnings and frequent missing sector counts.
- Some safe reports may lack particular source-view observations; safe status does not imply complete coverage of every metric.
- Leadership horizons roll through time, so near/far labels are regime-dependent.
- Analyst targets are secondary, subjective indicators.
- Valuation scenario ranges are mechanical EPS × P/E sensitivities, not probabilistic forecasts, expected returns, or FactSet target prices.
- Yahoo Finance `^GSPC` is an external data source that may be delayed, unavailable, or subject to provider terms; it is not part of the audited FactSet snapshot.
- Extracted observations can contain warnings or imperfect confidence despite retained provenance.
- Phase 3 deliberately has no 0–100 composite score or automated investment recommendation.

## 10. Future extension points

- Add multi-year history and a formally governed normalization methodology before introducing any composite score.
- Add richer provenance drill-downs that link chart points directly to field-level evidence.
- Add audited exports of filtered tables and chart data without mutating the source database.
- Add saved local research views while keeping them separate from the canonical Phase 2 database.
- Add broader estimate-breadth data if a governed full-universe source becomes available.
- Add more explicit extraction-quality coverage metrics and regression thresholds.
- Add visual and interaction regression tests for Streamlit pages.
- Add optional comparison databases or schema-version adapters behind the repository layer.

Any extension must preserve read-only database access, transparent units, honest missing data, source traceability, and the separation between research description and investment recommendation.
