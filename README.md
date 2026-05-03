# offrun

`offrun` is a planned Treasury buybacks and off-the-run liquidity project for the Treasury Deposit Channel research family.

The project asks whether Treasury buyback operations can improve liquidity in older off-the-run Treasury securities and reduce dealer balance-sheet pressure. It should be built as a bounded public-data event-study and measurement package, not as a broad Treasury-market microstructure project.

## Intended Scope

Core source families:

- Treasury buyback announcements and operation results.
- FiscalData Treasury Securities Buybacks dataset.
- FINRA TRACE Treasury aggregate volume and turnover data where public coverage supports it.
- New York Fed Primary Dealer Statistics for positions, financing, and fails.
- Treasury maturity and liquidity context reused from sibling projects where possible.

Sibling reuse should come first:

- [`tdcladder`](https://github.com/smkwray/tdcladder) for maturity/liquidity ladder context.
- [`buycurve`](https://github.com/smkwray/buycurve) for Treasury issuance composition and maturity context.
- [`liqsub`](https://github.com/smkwray/liqsub) for liquidity-plumbing diagnostics.
- [`rowflow`](https://github.com/smkwray/rowflow) for foreign official/private ROW accounting context if needed.

## Claim Boundary

Allowed claims:

- Treasury buybacks can be studied as dated interventions in targeted maturity sectors.
- Public data can support descriptive event windows around announcement and operation dates.
- Off-the-run liquidity should be interpreted with multiple proxies, including volume, turnover, dealer positions, financing, and fails.

Not allowed without stronger evidence:

- claims that buybacks caused broad domestic liquidity effects;
- claims that public TRACE aggregate data identify CUSIP-level liquidity;
- claims that targeted sectors are exogenous without pre-trend and control-bucket checks;
- claims that buybacks make long-duration debt money-like in the same way as Treasury bills.

## Local Initialization

Use an external virtual environment:

```bash
uv venv ~/venvs/offrun --python 3.11
source ~/venvs/offrun/bin/activate
```

The private `do/` folder contains the current build plan and orchestration prompts. It is ignored and must not be committed.
