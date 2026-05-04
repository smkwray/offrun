from __future__ import annotations

from offrun.io import read_csv
from offrun.real_sources import prepare_real_inputs
from offrun.trace_audit import audit_trace_source_granularity


def test_prepare_real_inputs_normalizes_fixture_siblings(temp_repo):
    outputs = prepare_real_inputs(
        temp_repo,
        sibling_root=temp_repo / "tests/fixtures/sibling_root",
        buybacks_input=temp_repo / "tests/fixtures/buybacks/buyback_operations_fixture.csv",
    )

    assert len(outputs) == 6
    assert (temp_repo / "data/imported/buybacks/buyback_operations.csv").exists()
    assert (temp_repo / "data/imported/tdcladder/monthly_ladder_panel.csv").exists()
    assert (temp_repo / "data/imported/buycurve/monthly_issuance_maturity_context.csv").exists()
    assert (temp_repo / "data/imported/liqsub/monthly_liquidity_plumbing.csv").exists()
    assert (temp_repo / "data/imported/trace/trace_treasury_aggregates.csv").exists()
    assert (temp_repo / "data/imported/dealer/primary_dealer_statistics.csv").exists()


def test_audit_trace_source_granularity_records_upgrade_path(temp_repo):
    output = audit_trace_source_granularity(
        temp_repo,
        sibling_root=temp_repo / "tests/fixtures/sibling_root",
    )
    rows = read_csv(output)

    assert len(rows) == 3
    finra_daily = next(
        row for row in rows if row["source_surface"] == "FINRA Treasury Daily Aggregate Statistics"
    )
    assert finra_daily["remaining_maturity_detail"].startswith("yes")
    assert finra_daily["on_off_run_detail"].startswith("yes")
    current = next(
        row for row in rows if row["source_surface"] == "tdcladder reused TRACE turnover"
    )
    assert current["on_off_run_detail"] == "no"
