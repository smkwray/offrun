from __future__ import annotations

from offrun.contracts import copy_sibling_outputs
from offrun.io import read_csv
from offrun.panels import (
    build_buyback_operations_panel,
    build_liquidity_context_panel,
    build_offrun_panel,
)
from offrun.reports import write_offrun_report
from offrun.validation import validate_claim_language


def test_build_buyback_operations_and_event_calendar(temp_repo):
    operations, calendar = build_buyback_operations_panel(
        temp_repo,
        input_path=temp_repo / "tests/fixtures/buybacks/buyback_operations_fixture.csv",
    )

    operation_rows = read_csv(operations)
    calendar_rows = read_csv(calendar)
    assert operation_rows[0]["acceptance_ratio"] == "0.75"
    assert len(calendar_rows) == 3 * 2 * 31
    assert {row["event_type"] for row in calendar_rows} == {"announcement", "operation"}


def test_build_full_fixture_panel_and_report(temp_repo):
    copy_sibling_outputs(
        temp_repo / "tests/fixtures/sibling_root",
        repo_root=temp_repo,
        overwrite=True,
        strict=True,
    )
    build_buyback_operations_panel(
        temp_repo,
        input_path=temp_repo / "tests/fixtures/buybacks/buyback_operations_fixture.csv",
    )
    build_liquidity_context_panel(
        temp_repo,
        trace_input=temp_repo / "tests/fixtures/trace/trace_aggregate_fixture.csv",
        dealer_input=temp_repo / "tests/fixtures/dealer/primary_dealer_fixture.csv",
    )
    panel, summary = build_offrun_panel(temp_repo)
    report = write_offrun_report(temp_repo)

    panel_rows = read_csv(panel)
    summary_rows = read_csv(summary)
    assert any(row["targeted_bucket"] == "1" for row in panel_rows)
    assert any(row["targeted_bucket"] == "0" for row in panel_rows)
    liquidity_rows = read_csv(temp_repo / "data/derived/liquidity_context_panel.csv")
    assert any(row["sibling_liquidity_weight"] for row in liquidity_rows)
    assert summary_rows

    failures = validate_claim_language(report.read_text(encoding="utf-8"), {
        "claim_boundary": {
            "required_report_phrases": ["descriptive market-liquidity evidence"],
            "forbidden_unqualified_phrases": ["proves causal liquidity effects"],
        }
    })
    assert failures == []
