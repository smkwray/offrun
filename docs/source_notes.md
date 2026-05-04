# source notes

## Sibling-first rule

`offrun` should reuse sibling outputs before downloading or transforming new data.

- `tdcladder`: maturity/liquidity ladder context and TRACE-turnover precedent surfaces.
- `buycurve`: Treasury issuance composition, bill share, weighted-average maturity, and maturity context.
- `liqsub`: TGA, reserves, MMFs, ON RRP, and broader liquidity-plumbing diagnostics.
- `rowflow`: optional rest-of-world sidecar only when useful for interpretation.

The source contracts live in `config/source_contracts.yml`. `offrun validate-sibling-sources --sibling-root .. --strict` checks that required sibling artifacts exist and have the expected columns. `offrun copy-sibling-outputs --sibling-root .. --overwrite` copies them into ignored `data/imported/` paths.

## Primary public sources

The starter does not download real data. Future adapters should use these public primary sources:

- FiscalData Treasury Securities Buybacks dataset for operation-level buyback data.
- TreasuryDirect buyback announcements/results for schedules, operation notices, and results.
- FINRA TRACE Treasury aggregate statistics only at the public aggregate level.
- New York Fed Primary Dealer Statistics for weekly positions, transactions, financing, and fails.
- H.15 / GSW rates only as optional controls.

## Public TRACE boundary

Public aggregate TRACE statistics can support descriptive volume or turnover context by broad category, depending on the exact public table used. They do not provide transaction-level or CUSIP-level liquidity evidence in this starter. Any production output that uses public aggregate TRACE data must label it as an aggregate proxy.

## Dealer statistics boundary

Primary Dealer Statistics are useful for positions, financing, and settlement-fails diagnostics. They are dealer-sector aggregates and should not be described as individual dealer balance sheets.

## Data policy

Do not commit real raw data, imported sibling outputs, derived analysis panels, reports, figures, or manifests. The public repository should contain code, contracts, docs, and tiny synthetic fixtures only.
