# Phase 3 Database Validation

The Phase 3 dashboard reads the canonical Phase 2 SQLite database. The
validation command audits that database without modifying it and prints a
Markdown-formatted report suitable for a terminal log or redirected file.

## Run the validator

From `factset-earnings-momentum-dashboard/`:

```bash
python scripts/validate_database.py
```

The default database is the repository sibling:

```text
../factset_earnings/factset_earnings.sqlite
```

To validate another copy:

```bash
python scripts/validate_database.py --db C:/path/to/factset_earnings.sqlite
```

The script uses only the Python standard library. It opens SQLite through a
`mode=ro` URI and also enables `query_only`, so validation queries cannot
mutate the database.

## What it validates

The report covers:

- total, safe, and partial report counts and date bounds;
- the `phase3_report_safe` status contract;
- all available GICS sectors;
- row, report, date, and safe-report coverage for every dashboard source view;
- missing-value rates for fields used by dashboard charts and tables;
- coverage of the latest near- and far-calendar-year bottom-up EPS periods;
- leadership horizon-roll dates, missing reports, and unclassified rows;
- index and sector guidance usability;
- warning counts by severity and warning code;
- visualizations that are unsupported or limited by the current data; and
- the known June 5, 2026 canonical earnings-growth discrepancy.

Missingness uses only rows attached to `phase3_report_safe = 1` reports. NULLs
are reported as NULLs; the validator never converts them to zero, fills gaps,
or interpolates observations.

## Current database baseline

The database audited for the initial Phase 3 build contains 28 reports from
January 9 through August 7, 2026. Twenty-seven are safe under the Phase 3
contract; the June 18 report is `PARTIAL` and excluded by default. The report
schedule is irregular, so dashboard momentum windows must use calendar dates
rather than row offsets.

All 11 GICS sectors are present. Core market valuation, margin, calendar-year
EPS, and sector growth data are broadly usable, but important constraints
remain:

- `reported_forward_12m_eps` and `derived_forward_12m_eps` are entirely NULL;
- sector five-year margin averages are entirely NULL;
- leadership is absent for May 1, June 5, and July 2, 2026;
- the leadership horizon rolls from CY2025/CY2026 to CY2026/CY2027 on April 17;
- sector guidance counts are incomplete and ambiguous, so missing counts must
  not be treated as zero;
- surprise histories contain material gaps;
- analyst rating percentages are available, but rating counts are entirely
  NULL; and
- `v_eps_revisions` contains Top-10 S&P 500 revision movers, not market-wide
  revision breadth.

The command calculates the exact live counts and rates on every run; its output
is authoritative if the database is refreshed after this baseline was written.

## Known canonical anomaly

For June 5, 2026, CY2026 earnings growth is stored as 2.2% in both
`v_index_metrics` and `v_period_growth`, while observation provenance includes
a narrative value of 22.8%. The validation command detects and reports this
discrepancy. It deliberately does not decide which observation should replace
the canonical value and does not correct Phase 2 data.

Until the extraction is reviewed, dashboard charts should visibly flag or
annotate that point rather than silently presenting it as an ordinary change.

## Exit behavior

- Exit code `0`: required database objects are present and the report ran.
- Exit code `1`: a required object is missing or a validation query failed.
- Exit code `2`: the database could not be found or opened.

Data limitations and the known anomaly are disclosed in the report but do not
cause a nonzero exit code. They are research-data quality findings, not evidence
that the read-only database connection failed.
