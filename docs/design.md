# offrun design

`offrun` is Project 4 in the Treasury Deposit Channel empirical project family: Treasury buybacks and off-the-run liquidity. It is a sidecar, not a replacement for the core TDC accounting estimator.

## Research object

Treasury buyback operations create dated interventions in older Treasury securities. The starter treats those interventions as an event-calendar problem:

1. normalize buyback operations by announcement date, operation date, security type, maturity bucket, offered amount, accepted amount, and acceptance ratio;
2. build event windows around announcement and operation dates;
3. join public aggregate liquidity proxies and dealer balance-sheet diagnostics to those windows;
4. compare targeted maturity buckets with nearby maturity buckets where the public data support that comparison.

## Unit of observation

The default analysis panel is an event-window panel. Each row is a buyback operation, an event type, a window date, and a comparison maturity bucket. Targeted buckets and nearby controls are kept in the same panel with an explicit `targeted_bucket` indicator.

The starter uses daily business-day windows for the fixture panel. Dealer data are often weekly in production, so future real-data builders should preserve the original frequency and avoid implying daily precision when weekly dealer statistics are the source.

## Minimal source pipeline

```text
buyback operations fixture or FiscalData/TreasuryDirect raw extract
  -> data/derived/buyback_operations.csv
  -> data/derived/buyback_event_calendar.csv

public aggregate TRACE fixture/raw extract
NY Fed Primary Dealer Statistics fixture/raw extract
sibling maturity/liquidity context copied into data/imported/
  -> data/derived/trace_liquidity_context.csv
  -> data/derived/dealer_liquidity_context.csv
  -> data/derived/liquidity_context_panel.csv

buyback_event_calendar + liquidity_context_panel
  -> data/derived/offrun_panel.csv
  -> output/tables/buyback_event_summary.csv
  -> output/reports/offrun_accounting_report.md
```

## Design A: event windows

For each buyback operation, build event windows around both announcement and operation dates. The fixture build uses `-10` to `+20` business days. The event-day index is descriptive; it does not by itself identify causal effects.

## Design B: targeted versus nearby buckets

The starter includes a conservative comparison-bucket map in `config/variables.yml`. For example, a targeted `7-10y` bucket can be compared with `3-7y` and `10-20y` buckets if the source panel has observable rows for those buckets. These comparisons are credibility checks, not proof of exogeneity.

## Design C: dose response placeholder

The operations panel computes offered amount, accepted amount, and acceptance ratio. A future real-data pass can add accepted amount scaled by outstanding off-the-run stock or recent turnover once source coverage supports the denominator.

## Output interpretation

The generated report is required to describe the package as descriptive market-liquidity evidence. The validation gate rejects unqualified causal pass-through language and CUSIP-level liquidity language from public aggregate TRACE data.
