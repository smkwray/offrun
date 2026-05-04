# claim boundaries

`offrun` is a market-liquidity sidecar for the Treasury Deposit Channel project family. It does not directly estimate TDC and it does not identify domestic deposit pass-through.

## Allowed language

The package may describe:

- descriptive market-liquidity evidence;
- event windows around Treasury buyback announcement and operation dates;
- targeted maturity-bucket versus nearby-bucket comparisons when supported by public data;
- dealer-position, financing, and fails diagnostics;
- public aggregate TRACE volume or turnover proxies when clearly labeled as aggregate proxies.

## Forbidden without stronger evidence

The package must not claim:

- causal domestic liquidity pass-through;
- CUSIP-level liquidity from public TRACE aggregate data;
- exogeneity of Treasury target selection without pre-trend and control-bucket checks;
- that buybacks make long-duration debt money-like in the same way as Treasury bills;
- that volume alone is liquidity.

## Automated gate

`offrun validate-offrun-package --strict` reads `output/reports/offrun_accounting_report.md` and enforces two language checks:

1. The report must include `descriptive market-liquidity evidence`.
2. The report must not include forbidden unqualified phrases listed in `config/project.yml`.

The gate is intentionally simple in the starter. Future versions may add richer claim-boundary linting, pre-trend checks, and source-coverage thresholds.
