# offrun

`offrun` builds a bounded Treasury buybacks and off-the-run liquidity evidence package for the Treasury Deposit Channel project family.

The core question is whether Treasury buyback operations show up in publicly observable off-the-run Treasury liquidity proxies or dealer balance-sheet pressure diagnostics. The package is deliberately conservative: it produces descriptive market-liquidity evidence around dated buyback announcement and operation windows. It is not a causal domestic-liquidity pass-through estimator and it does not claim CUSIP-level liquidity from public aggregate TRACE data.

## Scope

The starter implements real CLI code paths against tiny synthetic fixtures. It does not include real raw data. The source strategy is:

1. Reuse sibling outputs first:
   - `tdcladder` for maturity/liquidity ladder context and TRACE-turnover precedents;
   - `buycurve` for Treasury issuance composition and maturity context;
   - `liqsub` for liquidity-plumbing diagnostics;
   - `rowflow` only as an optional rest-of-world sidecar.
2. Use public primary sources only after the reusable sibling artifacts are unavailable or insufficient:
   - FiscalData Treasury Securities Buybacks;
   - TreasuryDirect buyback announcements/results;
   - FINRA TRACE Treasury aggregate statistics at the public aggregate level only;
   - New York Fed Primary Dealer Statistics;
   - H.15 / GSW yield and rate controls only if needed.

## Install

Use an external virtual environment. Do not create a repo-local virtual environment.

```bash
python -m venv ~/venvs/offrun
source ~/venvs/offrun/bin/activate
python -m pip install -e '.[dev]'
```

## Smoke checks

```bash
python -m pytest -q
ruff check .
offrun validate-config
make smoke-fixtures
```

`make smoke-fixtures` builds a complete no-external-data package from the synthetic CSV files under `tests/fixtures/`.

## CLI command map

```bash
offrun validate-config
offrun validate-sibling-sources --sibling-root .. --strict
offrun copy-sibling-outputs --sibling-root .. --overwrite
offrun build-buyback-operations-panel
offrun build-liquidity-context-panel
offrun build-offrun-panel
offrun write-offrun-report
offrun write-output-manifest
offrun validate-offrun-package --strict
```

All commands accept an optional global `--repo-root <path>` argument before the subcommand for tests and scripted builds.

## Generated local outputs

The fixture smoke build writes local artifacts under ignored `data/` and `output/` paths:

```text
data/derived/buyback_operations.csv
data/derived/buyback_event_calendar.csv
data/derived/trace_liquidity_context.csv
data/derived/dealer_liquidity_context.csv
data/derived/liquidity_context_panel.csv
data/derived/offrun_panel.csv
output/tables/buyback_event_summary.csv
output/tables/source_inventory.csv
output/reports/offrun_accounting_report.md
output/figures/buyback_timeline.svg
output/figures/targeted_bucket_event_windows.svg
output/manifests/offrun_manifest.json
```

These generated files are intentionally ignored by git. The repository should contain code, contracts, docs, and tiny fixtures only.

## Claim boundary

Allowed claims:

- descriptive market-liquidity evidence;
- event windows around buyback announcement and operation dates;
- targeted maturity-bucket versus nearby-bucket comparisons when supported;
- dealer-position, fails, and financing diagnostics.

Forbidden without stronger evidence:

- causal domestic liquidity pass-through claims;
- CUSIP-level liquidity claims from public TRACE aggregate data;
- exogeneity claims without pre-trend and control-bucket checks;
- claims that buybacks make long-duration debt money-like in the same way as Treasury bills.

`offrun validate-offrun-package --strict` enforces the report language gate. The report must include the phrase `descriptive market-liquidity evidence` and must not include unqualified phrases such as `proves causal liquidity effects` or `identifies domestic liquidity pass-through`.
