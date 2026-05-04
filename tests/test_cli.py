from __future__ import annotations

from offrun.cli import main


def run_cli(temp_repo, *args: str) -> int:
    return main(["--repo-root", str(temp_repo), *args])


def test_cli_fixture_smoke(temp_repo):
    fixture_root = temp_repo / "tests/fixtures"

    assert run_cli(temp_repo, "validate-config") == 0
    assert run_cli(
        temp_repo,
        "validate-sibling-sources",
        "--sibling-root",
        str(fixture_root / "sibling_root"),
        "--strict",
    ) == 0
    assert run_cli(
        temp_repo,
        "copy-sibling-outputs",
        "--sibling-root",
        str(fixture_root / "sibling_root"),
        "--overwrite",
    ) == 0
    assert run_cli(
        temp_repo,
        "build-buyback-operations-panel",
        "--input",
        str(fixture_root / "buybacks/buyback_operations_fixture.csv"),
    ) == 0
    assert run_cli(
        temp_repo,
        "build-liquidity-context-panel",
        "--trace-input",
        str(fixture_root / "trace/trace_aggregate_fixture.csv"),
        "--dealer-input",
        str(fixture_root / "dealer/primary_dealer_fixture.csv"),
    ) == 0
    assert run_cli(temp_repo, "build-offrun-panel") == 0
    assert run_cli(temp_repo, "write-offrun-report") == 0
    assert run_cli(temp_repo, "write-output-manifest") == 0
    assert run_cli(temp_repo, "validate-offrun-package", "--strict") == 0
