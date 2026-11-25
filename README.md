# offrun

`offrun` builds a descriptive evidence package on whether U.S. Treasury buybacks show up in public measures of off-the-run Treasury liquidity (older securities that are no longer the newest issue at their maturity) and of dealer balance-sheet pressure. It supports research on the Treasury Deposit Component (TDC), the part of the change in bank deposits that comes from Treasury payments and trades in Treasury securities.

The results are event-window comparisons on aggregate public data. They do not measure liquidity of individual securities (CUSIP level), and they are not causal estimates of buybacks' effect on domestic liquidity. A self-contained build runs from test fixtures; the real build also needs outputs from the sibling repositories [`tdcladder`](https://github.com/smkwray/tdcladder), [`buycurve`](https://github.com/smkwray/buycurve) and [`liqsub`](https://github.com/smkwray/liqsub), checked out next to this one.

## What it builds

For each buyback operation, `offrun` builds windows around the announcement and operation dates and compares the targeted maturity bucket with nearby buckets. It joins those windows to aggregate trading volume and turnover from FINRA TRACE and to primary dealer positions, financing and settlement fails. It then adds pre-trend and placebo checks and gives each event an evidence grade based on source coverage and those checks. [docs/design.md](docs/design.md) describes the design.

## Data sources

| Source | Used for |
|---|---|
| [Treasury FiscalData buyback operations](https://fiscaldata.treasury.gov/datasets/treasury-securities-buybacks/) | Operation dates, security type, maturity bucket, offered and accepted amounts (downloaded) |
| [FINRA TRACE Treasury aggregates](https://www.finra.org/filing-reporting/trace/data/trace-treasury-aggregates/about) | Daily aggregate volume by maturity and on/off-the-run status for nominal coupons and Treasury Inflation-Protected Securities (TIPS) (downloaded) |
| [New York Fed Primary Dealer Statistics](https://www.newyorkfed.org/markets/counterparties/primary-dealers-statistics) | Weekly dealer positions, financing and fails, read from `buycurve` |
| `tdcladder` | Treasury supply by maturity bucket, and TRACE turnover when the direct FINRA files are unavailable |
| `buycurve` | Issuance and maturity composition, primary dealer context |
| `liqsub` | Monthly liquidity-substitution panel |
| [`rowflow`](https://github.com/smkwray/rowflow) (optional) | Foreign net purchases of Treasuries, as context |

TRACE is FINRA's Trade Reporting and Compliance Engine. [docs/source_notes.md](docs/source_notes.md) has more on each source.

## Install and run

Requires Python 3.11 or later. The Makefile's default interpreter path does not exist on other machines, so pass `PYTHON` explicitly.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q

make smoke-fixtures PYTHON=python   # full package from the synthetic data in tests/fixtures/, no downloads
make real-package PYTHON=python     # real data; set SIBLING_ROOT if the sibling repos are not in ..
```

Each make target runs a sequence of `offrun` subcommands; `offrun --help` lists them.

## Outputs

Builds write to `data/` and `output/`, which are not tracked.

- `data/derived/`: normalized buyback operations, the event calendar, TRACE and dealer context, and the event-window panel (`offrun_panel.csv`).
- `output/tables/`: event summaries, source reconciliation, pre-trend and placebo diagnostics, a ranked results triage, the evidence ledger, and coverage and source-granularity audits.
- `output/reports/`: `offrun_accounting_report.md` and `offrun_findings_report.md`.
- `output/figures/`: buyback timeline and event-window charts (SVG).
- `output/manifests/offrun_manifest.json`: a manifest of the generated files.

## Limits

- TRACE data are public aggregates by maturity bucket, not CUSIP-level or transaction-level data, and volume is a proxy for liquidity, not liquidity itself.
- Targeted-versus-nearby comparisons and pre-trend and placebo checks test credibility; they do not show that buyback targets were chosen independently of market conditions.
- Dealer positions are mapped to maturity buckets only where the New York Fed series allow; financing and fails are aggregate Treasury and TIPS series.
- The package does not show that buybacks make long-duration debt money-like in the way Treasury bills are.

## License

MIT; see [LICENSE](LICENSE).
