# source notes

## Sibling-first rule

`offrun` should reuse sibling outputs before downloading or transforming new data.

- [`tdcladder`](https://github.com/smkwray/tdcladder): maturity/liquidity ladder context and TRACE-turnover precedent surfaces.
- [`buycurve`](https://github.com/smkwray/buycurve): Treasury issuance composition, bill share, weighted-average maturity, and maturity context.
- [`liqsub`](https://github.com/smkwray/liqsub): TGA, reserves, MMFs, ON RRP, and broader liquidity-plumbing diagnostics.
- [`rowflow`](https://github.com/smkwray/rowflow): optional rest-of-world sidecar only when useful for interpretation.

The source contracts live in `config/source_contracts.yml`. `offrun validate-sibling-sources --sibling-root .. --strict` checks that required sibling artifacts exist and have the expected columns. `offrun copy-sibling-outputs --sibling-root .. --overwrite` copies them into ignored `data/imported/` paths.

## Primary public sources

The real backend can download and normalize FiscalData buyback operations with
`offrun download-fiscaldata-buybacks` or as part of
`offrun prepare-real-inputs --download-buybacks`. Other source families are
reused from sibling outputs before new downloaders are added:

- FiscalData Treasury Securities Buybacks dataset for operation-level buyback data.
- TreasuryDirect buyback announcements/results for schedules, operation notices, and results.
- FINRA TRACE Treasury aggregate statistics only at the public aggregate level.
- New York Fed Primary Dealer Statistics for weekly positions, transactions, financing, and fails.
- H.15 / GSW rates only as optional controls.

## Real backend inputs

`offrun prepare-real-inputs --sibling-root .. --download-buybacks` writes ignored
normalized inputs under `data/imported/`:

- FiscalData buyback operations into `data/imported/buybacks/buyback_operations.csv`.
- [`tdcladder`](https://github.com/smkwray/tdcladder) bucket-level Treasury stock/liquidity context into
  `data/imported/tdcladder/monthly_ladder_panel.csv`.
- [`tdcladder`](https://github.com/smkwray/tdcladder) public aggregate TRACE turnover into
  `data/imported/trace/trace_treasury_aggregates.csv`.
- [`buycurve`](https://github.com/smkwray/buycurve) issuance/maturity context into
  `data/imported/buycurve/monthly_issuance_maturity_context.csv`.
- [`buycurve`](https://github.com/smkwray/buycurve) cleaned New York Fed primary-dealer positions into
  `data/imported/dealer/primary_dealer_statistics.csv`.
- [`buycurve`](https://github.com/smkwray/buycurve) raw New York Fed primary-dealer time series for aggregate Treasury
  financing and fails into the same dealer context file.
- [`liqsub`](https://github.com/smkwray/liqsub) monthly plumbing context into
  `data/imported/liqsub/monthly_liquidity_plumbing.csv`.

The normalized imports are local build products, not public repository content.

The generated triage outputs are also local build products. `results_triage.csv`
and `offrun_findings_report.md` classify rows as descriptive diagnostics only;
they do not promote causal language or CUSIP-level liquidity claims.

## Public TRACE boundary

Public aggregate TRACE statistics can support descriptive volume or turnover context by broad category, depending on the exact public table used. They do not provide transaction-level or CUSIP-level liquidity evidence. Any production output that uses public aggregate TRACE data must label it as an aggregate proxy.

## Dealer statistics boundary

Primary Dealer Statistics are useful for positions, financing, and settlement-fails diagnostics. They are dealer-sector aggregates and should not be described as individual dealer balance sheets. Net-position rows are mapped to maturity buckets where the source series support that mapping; financing and fails rows are aggregate Treasury/TIPS diagnostics, not maturity-bucket-specific observations.

## Data policy

Do not commit real raw data, imported sibling outputs, derived analysis panels, reports, figures, or manifests. The public repository should contain code, contracts, docs, and tiny synthetic fixtures only.
