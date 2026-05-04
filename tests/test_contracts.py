from __future__ import annotations

from offrun.contracts import copy_sibling_outputs, validate_sibling_sources


def test_validate_fixture_sibling_sources_strict(temp_repo):
    statuses = validate_sibling_sources(
        temp_repo / "tests/fixtures/sibling_root",
        repo_root=temp_repo,
        strict=True,
    )

    required = [status for status in statuses if status.required]
    assert required
    assert all(status.ok for status in required)
    assert (temp_repo / "output/tables/source_inventory.csv").exists()


def test_copy_fixture_sibling_outputs(temp_repo):
    copied = copy_sibling_outputs(
        temp_repo / "tests/fixtures/sibling_root",
        repo_root=temp_repo,
        overwrite=True,
        strict=True,
    )

    assert copied
    assert (temp_repo / "data/imported/tdcladder/monthly_ladder_panel.csv").exists()
    assert (temp_repo / "data/imported/buycurve/monthly_issuance_maturity_context.csv").exists()
    assert (temp_repo / "data/imported/liqsub/monthly_liquidity_plumbing.csv").exists()
