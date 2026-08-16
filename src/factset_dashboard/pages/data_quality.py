"""Report health, extraction warnings, and field-level provenance."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from factset_dashboard import models, ui
from factset_dashboard.filters import DashboardContext, at_report_date


def render(bundle: dict[str, pd.DataFrame], context: DashboardContext) -> None:
    ui.page_header(
        "Audit trail",
        "Data Quality & Provenance",
        "Inspect report safety, extraction warnings, and the source evidence behind canonical analytical fields.",
    )
    reports = bundle.get("report_health", bundle["reports"])
    warnings = bundle.get("all_extraction_warnings", bundle["extraction_warnings"])
    provenance = bundle["observation_provenance"]
    safe_count = int(reports["phase3_report_safe"].eq(1).sum())
    partial_count = int(reports["status"].eq("PARTIAL").sum())
    cards = st.columns(4)
    with cards[0]:
        ui.metric_card("Reports in scope", len(reports), kind="count")
    with cards[1]:
        ui.metric_card("Safe reports", safe_count, kind="count")
    with cards[2]:
        ui.metric_card("Partial reports", partial_count, kind="count")
    with cards[3]:
        ui.metric_card("Warnings", len(warnings), kind="count")

    st.subheader("Report health")
    health = reports[
        ["report_date", "filename", "status", "page_count", "phase3_report_safe", "schema_version", "extractor_version"]
    ].sort_values("report_date", ascending=False)
    health = health.rename(
        columns={
            "report_date": "Report date",
            "filename": "Filename",
            "status": "Status",
            "page_count": "Pages",
            "phase3_report_safe": "Phase 3 safe",
            "schema_version": "Schema",
            "extractor_version": "Extractor",
        }
    )
    st.dataframe(ui.dataframe_for_display(health), hide_index=True, width="stretch")

    st.subheader("Warning summary")
    summary = models.warning_summary(warnings)
    code_options = sorted(summary["code"].dropna().unique()) if not summary.empty else []
    severity_options = sorted(summary["severity"].dropna().unique()) if not summary.empty else []
    left, right = st.columns(2)
    with left:
        selected_codes = st.multiselect("Warning codes", code_options, key="quality_warning_codes")
    with right:
        selected_severity = st.multiselect("Severity", severity_options, key="quality_warning_severity")
    filtered_summary = summary
    if selected_codes:
        filtered_summary = filtered_summary.loc[filtered_summary["code"].isin(selected_codes)]
    if selected_severity:
        filtered_summary = filtered_summary.loc[filtered_summary["severity"].isin(selected_severity)]
    st.dataframe(
        ui.dataframe_for_display(
            filtered_summary.rename(
                columns={
                    "report_date": "Report date",
                    "code": "Warning code",
                    "severity": "Severity",
                    "warning_count": "Count",
                }
            ),
            {"Count": "count"},
        ),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Warning detail"):
        warning_detail = warnings.copy()
        if selected_codes:
            warning_detail = warning_detail.loc[warning_detail["code"].isin(selected_codes)]
        if selected_severity:
            warning_detail = warning_detail.loc[warning_detail["severity"].isin(selected_severity)]
        detail_columns = ["report_date", "code", "severity", "message", "source_filename"]
        st.dataframe(ui.dataframe_for_display(warning_detail[detail_columns]), hide_index=True, width="stretch")

    st.subheader("Observation provenance")
    selected = at_report_date(provenance, context.selected_report_date)
    table_options = sorted(selected["table_name"].dropna().unique())
    table_name = st.selectbox("Canonical table", table_options, index=0, key="provenance_table") if table_options else None
    if table_name:
        selected = selected.loc[selected["table_name"].eq(table_name)]
    field_options = sorted(selected["field_name"].dropna().unique())
    fields = st.multiselect("Fields", field_options, key="provenance_fields")
    if fields:
        selected = selected.loc[selected["field_name"].isin(fields)]
    confidence_options = sorted(selected["confidence"].dropna().unique())
    confidences = st.multiselect("Confidence", confidence_options, key="provenance_confidence")
    if confidences:
        selected = selected.loc[selected["confidence"].isin(confidences)]
    columns = [
        "source_filename",
        "source_page",
        "table_name",
        "observation_key",
        "field_name",
        "section_title",
        "chart_title",
        "raw_label",
        "raw_text",
        "extraction_method",
        "confidence",
    ]
    maximum_rows = 500
    st.dataframe(ui.dataframe_for_display(selected.reindex(columns=columns).head(maximum_rows)), hide_index=True, width="stretch")
    if len(selected) > maximum_rows:
        st.caption(f"Showing the first {maximum_rows:,} of {len(selected):,} matching provenance rows. Narrow the filters to inspect a specific field.")
    elif selected.empty:
        ui.note("No provenance rows match the selected report and filters.", quality=True)
    st.caption(f"Database opened read-only: {context.database_path}")
