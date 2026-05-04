# offrun design

`offrun` is a Treasury buybacks and off-the-run liquidity package for Treasury Deposit Channel (TDC) research. It is a market-functioning sidecar, not a replacement for a core TDC accounting estimator.

## Research object

Treasury buyback operations create dated interventions in older Treasury securities. The package treats those interventions as an event-calendar problem:

1. normalize buyback operations by announcement date, operation date, security type, maturity bucket, offered amount, accepted amount, and acceptance ratio;
2. build event windows around announcement and operation dates;
3. join public aggregate liquidity proxies and dealer balance-sheet diagnostics to those windows;
4. compare targeted maturity buckets with nearby maturity buckets where the public data support that comparison.

## Unit of observation

The default analysis panel is an event-window panel. Each row is a buyback operation, an event type, a window date, and a comparison maturity bucket. Targeted buckets and nearby controls are kept in the same panel with an explicit `targeted_bucket` indicator.

The fixture build uses daily business-day windows. Real TRACE context uses public
FINRA daily Treasury aggregate statistics when those public files are available.
Those files preserve aggregate maturity and on/off-run fields for Nominal Coupons
and TIPS. Real dealer context is weekly aggregate Primary Dealer Statistics. The
event-window join preserves those sources as aggregate context and does not imply
CUSIP-level or transaction-level TRACE precision.

## Minimal source pipeline

```text
buyback operations fixture or FiscalData/TreasuryDirect raw extract
  -> data/derived/buyback_operations.csv
  -> data/derived/buyback_event_calendar.csv

public aggregate TRACE fixture/raw extract or [`tdcladder`](https://github.com/smkwray/tdcladder) public aggregate TRACE context
NY Fed Primary Dealer Statistics fixture/raw extract or [`buycurve`](https://github.com/smkwray/buycurve) cleaned dealer context
sibling maturity/liquidity context copied into data/imported/
  -> data/derived/trace_liquidity_context.csv
  -> data/derived/dealer_liquidity_context.csv
  -> data/derived/liquidity_context_panel.csv

buyback_event_calendar + liquidity_context_panel
  -> data/derived/offrun_panel.csv
  -> output/tables/buyback_event_summary.csv
  -> output/tables/pretrend_diagnostics.csv
  -> output/tables/placebo_diagnostics.csv
  -> output/tables/evidence_ledger.csv
  -> output/reports/offrun_accounting_report.md
```

## Design A: event windows

For each buyback operation, build event windows around both announcement and operation dates. The fixture build uses `-10` to `+20` business days. The event-day index is descriptive; it does not by itself identify causal effects.

## Design B: targeted versus nearby buckets

The package includes a conservative comparison-bucket map in `config/variables.yml`. For example, a targeted `7-10y` bucket can be compared with `3-7y` and `10-20y` buckets if the source panel has observable rows for those buckets. These comparisons are credibility checks, not proof of exogeneity.

## Design C: dose response diagnostics

The operations panel computes offered amount, accepted amount, and acceptance
ratio. Event rows also report accepted amount scaled by sibling outstanding
stock, sibling liquidity-weighted supply, and same-window TRACE volume when
those denominators are available. These are diagnostic intensity measures, not
structural treatment-dose estimates.

## Design D: pretrend, placebo, and evidence grading

`pretrend_diagnostics.csv` separates early-pre and late-pre changes from the
post-event readout. `placebo_diagnostics.csv` applies the same targeted-versus-
control logic to the pre-event window. `evidence_ledger.csv` turns source support,
pretrend/placebo warnings, and dealer coverage into a compact evidence grade.

## Output interpretation

The generated report is required to describe the package as descriptive market-liquidity evidence. The validation gate rejects unqualified causal pass-through language and CUSIP-level liquidity language from public aggregate TRACE data.

## TRACE source-quality extension

The package includes a TRACE source-granularity audit plus direct FINRA daily
aggregate file acquisition and conversion. The real package falls back to
`tdcladder` broad public aggregate turnover only when direct FINRA files are not
available. Even with direct FINRA aggregate imports, the evidence remains
aggregate public volume/turnover context, not CUSIP-level liquidity or causal
pass-through evidence.
