"""Report and figure generation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .config import load_config
from .io import OffrunError, as_float, format_number, read_csv, write_csv, write_text


def _source_inventory_fallback(repo_root: Path, output_path: Path) -> None:
    """Write a minimal public-source inventory when sibling validation has not run."""

    rows = [
        {
            "source_family": "fixture_buybacks",
            "artifact": "buyback_operations_fixture",
            "source_path": str(
                repo_root / "tests/fixtures/buybacks/buyback_operations_fixture.csv"
            ),
            "import_path": "",
            "required": "false",
            "exists": "true",
            "row_count": "fixture",
            "missing_columns": "",
            "status": "fixture_only",
        },
        {
            "source_family": "fixture_trace",
            "artifact": "trace_aggregate_fixture",
            "source_path": str(repo_root / "tests/fixtures/trace/trace_aggregate_fixture.csv"),
            "import_path": "",
            "required": "false",
            "exists": "true",
            "row_count": "fixture",
            "missing_columns": "",
            "status": "fixture_only",
        },
        {
            "source_family": "fixture_dealer",
            "artifact": "primary_dealer_fixture",
            "source_path": str(repo_root / "tests/fixtures/dealer/primary_dealer_fixture.csv"),
            "import_path": "",
            "required": "false",
            "exists": "true",
            "row_count": "fixture",
            "missing_columns": "",
            "status": "fixture_only",
        },
    ]
    fieldnames = [
        "source_family",
        "artifact",
        "source_path",
        "import_path",
        "required",
        "exists",
        "row_count",
        "missing_columns",
        "status",
    ]
    write_csv(output_path, rows, fieldnames)


def _write_timeline_svg(rows: list[dict[str, str]], output_path: Path, *, fixture: bool) -> None:
    """Write a small SVG timeline without external plotting dependencies."""

    if not rows:
        raise OffrunError("Cannot write buyback timeline with no operations")
    height = 60 + 34 * len(rows)
    width = 760
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 760 {height}">',
        '<rect width="760" height="100%" fill="white"/>',
        '<text x="20" y="28" font-size="16" font-family="sans-serif">'
        f"{'Synthetic' if fixture else 'Treasury'} buyback operation timeline</text>",
    ]
    max_accepted = max(as_float(row.get("accepted_amount_usd_millions")) for row in rows) or 1.0
    for index, row in enumerate(rows):
        y = 58 + 34 * index
        accepted = as_float(row.get("accepted_amount_usd_millions"))
        bar_width = int(320 * accepted / max_accepted)
        label = (
            f"{row.get('operation_date', '')} · {row.get('maturity_bucket', '')} · "
            f"accepted {row.get('accepted_amount_usd_millions', '')} USD millions"
        )
        lines.extend(
            [
                f'<text x="20" y="{y + 14}" font-size="12" font-family="sans-serif">'
                f"{label}</text>",
                f'<rect x="400" y="{y}" width="{bar_width}" height="18" fill="#8aa"/>',
            ]
        )
    lines.append("</svg>")
    write_text(output_path, "\n".join(lines) + "\n")


def _write_event_svg(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write a compact SVG for event-window turnover changes."""

    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("targeted_bucket") != "1":
            continue
        if row.get("post_minus_pre_trace_turnover"):
            grouped[row.get("target_maturity_bucket", "unknown")].append(
                as_float(row.get("post_minus_pre_trace_turnover"))
            )
    means = {
        bucket: sum(values) / len(values)
        for bucket, values in grouped.items()
        if values
    }
    height = 80 + 36 * max(len(means), 1)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" '
        f'viewBox="0 0 760 {height}">',
        '<rect width="760" height="100%" fill="white"/>',
        '<text x="20" y="28" font-size="16" font-family="sans-serif">'
        "Targeted bucket event-window summary</text>",
        '<line x1="380" x2="380" y1="48" y2="95%" stroke="#555" stroke-width="1"/>',
    ]
    if not means:
        lines.append(
            '<text x="20" y="64" font-size="12" font-family="sans-serif">'
            "No non-missing turnover changes in fixture window.</text>"
        )
    max_abs = max((abs(value) for value in means.values()), default=1.0) or 1.0
    for index, (bucket, value) in enumerate(sorted(means.items())):
        y = 58 + 34 * index
        width = int(220 * abs(value) / max_abs)
        x = 380 if value >= 0 else 380 - width
        lines.extend(
            [
                f'<text x="20" y="{y + 14}" font-size="12" font-family="sans-serif">'
                f"{bucket}: {value:.6f}</text>",
                f'<rect x="{x}" y="{y}" width="{width}" height="18" fill="#8aa"/>',
            ]
        )
    lines.append("</svg>")
    write_text(output_path, "\n".join(lines) + "\n")


def _write_count_svg(
    rows: list[dict[str, str]],
    output_path: Path,
    *,
    field: str,
    title: str,
) -> None:
    counts = _status_counts(rows, field)
    height = 80 + 34 * max(len(counts), 1)
    width = 760
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="760" height="100%" fill="white"/>',
        f'<text x="20" y="28" font-size="16" font-family="sans-serif">{title}</text>',
    ]
    if not counts:
        lines.append(
            '<text x="20" y="64" font-size="12" font-family="sans-serif">No rows.</text>'
        )
    max_count = max(counts.values(), default=1)
    for index, (label, count) in enumerate(counts.items()):
        y = 58 + 34 * index
        bar_width = int(420 * count / max_count) if max_count else 0
        lines.extend(
            [
                f'<text x="20" y="{y + 14}" font-size="12" font-family="sans-serif">'
                f"{label}: {count}</text>",
                f'<rect x="280" y="{y}" width="{bar_width}" height="18" fill="#8aa"/>',
            ]
        )
    lines.append("</svg>")
    write_text(output_path, "\n".join(lines) + "\n")


def _status_counts(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.get(field, "") or "missing"] += 1
    return dict(sorted(counts.items()))


def _format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in counts.items()) or "none"


def _trace_source_note(trace_rows: list[dict[str, str]]) -> str:
    source_families = {row.get("source_family", "") for row in trace_rows}
    has_finra_direct = any(source.startswith("finra_treasury_") for source in source_families)
    if has_finra_direct:
        return (
            "Direct FINRA Treasury aggregate rows are used when locally available. "
            "They preserve public aggregate maturity and on/off-run groupings, but "
            "remain aggregate public volume/turnover proxies rather than "
            "CUSIP-level or transaction-level liquidity data."
        )
    return (
        "TRACE turnover is a broad public aggregate proxy repeated across analysis "
        "buckets for event-window alignment; it is not maturity-bucket or "
        "CUSIP-level liquidity."
    )


def _top_rows(rows: list[dict[str, str]], count: int = 8) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: as_float(row.get("triage_rank")))[:count]


def _markdown_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    if not rows:
        return "No rows available.\n"
    header = "| " + " | ".join(fields) + " |"
    divider = "| " + " | ".join("---" for _ in fields) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return "\n".join([header, divider, *body]) + "\n"


def _write_findings_report(
    output_path: Path,
    *,
    operation_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    triage_rows: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
    diagnostics_rows: list[dict[str, str]],
) -> None:
    claim_counts = _status_counts(triage_rows, "claim_status")
    coverage_counts = _status_counts(coverage_rows, "coverage_status")
    diagnostic_counts = _status_counts(diagnostics_rows, "trace_diagnostic_status")
    completed_operations = len({row.get("operation_id", "") for row in operation_rows})
    diagnostic_ready = sum(
        1 for row in diagnostics_rows if row.get("trace_diagnostic_status") == "diagnostic_ready"
    )
    supportive = [row for row in triage_rows if row.get("claim_status") == "supportive_diagnostic"]
    mixed = [row for row in triage_rows if row.get("claim_status") == "mixed_diagnostic"]
    avg_intensity_values = [
        as_float(row.get("buyback_intensity"))
        for row in triage_rows
        if row.get("buyback_intensity")
    ]
    avg_intensity = (
        sum(avg_intensity_values) / len(avg_intensity_values) if avg_intensity_values else None
    )
    trace_source_note = _trace_source_note(trace_rows)

    top_table = _markdown_table(
        _top_rows(triage_rows),
        [
            "triage_rank",
            "operation_id",
            "event_type",
            "target_maturity_bucket",
            "claim_status",
            "signal_score",
            "targeted_minus_control_trace_turnover_change",
            "post_minus_pre_fails",
            "buyback_intensity",
            "coverage_status",
        ],
    )
    text = f"""# offrun findings report

This report summarizes **descriptive market-liquidity evidence** from the current
real-source build. It is a diagnostic screen, not a causal estimate.

## Readout

- Completed buyback operations: {completed_operations}
- Event diagnostics with targeted-versus-control TRACE support: {diagnostic_ready}
- Claim-status counts: {_format_counts(claim_counts)}
- Coverage-status counts: {_format_counts(coverage_counts)}
- TRACE diagnostic-status counts: {_format_counts(diagnostic_counts)}
- Supportive diagnostic rows: {len(supportive)}
- Mixed diagnostic rows: {len(mixed)}
- Average available buyback intensity: {format_number(avg_intensity)}

## Top diagnostic rows

{top_table}
## Interpretation

`supportive_diagnostic` means the row has a positive targeted-minus-control TRACE
turnover change and either lower fails or lower relative dealer net positions in
the same descriptive window. `mixed_diagnostic` means one proxy moves in a
potentially supportive direction while another is unavailable or points the
other way. `coverage_limited` means the source support is too thin for that row
to carry interpretive weight.

{trace_source_note} Dealer financing and fails are aggregate Treasury/TIPS
diagnostics. These outputs should therefore be read as market functioning screens
around Treasury buybacks, not as CUSIP-level liquidity evidence or causal
pass-through estimates.

`output/tables/trace_source_granularity_audit.csv` records the next source
upgrade path. FINRA's public daily and monthly aggregate Treasury files advertise
remaining-maturity and on/off-run groupings for Nominal Coupons and TIPS, but
they remain aggregate public files rather than CUSIP-level or transaction-level
liquidity data.
"""
    write_text(output_path, text)


def write_offrun_report(
    repo_root: Path | str | None = None,
    *,
    panel_path: Path | str | None = None,
    summary_path: Path | str | None = None,
    output_md: Path | str | None = None,
    figure_dir: Path | str | None = None,
    table_dir: Path | str | None = None,
) -> Path:
    """Write the markdown report, source inventory fallback, and SVG figures."""

    config = load_config(repo_root)
    panel_file = Path(panel_path) if panel_path is not None else config.path("offrun_panel")
    summary_file = (
        Path(summary_path)
        if summary_path is not None
        else config.path("buyback_event_summary")
    )
    report_file = Path(output_md) if output_md is not None else config.path("report")
    figures = Path(figure_dir) if figure_dir is not None else config.repo_root / "output/figures"
    tables = Path(table_dir) if table_dir is not None else config.repo_root / "output/tables"

    panel_rows = read_csv(panel_file)
    summary_rows = read_csv(summary_file)
    operation_rows = read_csv(config.path("buyback_operations"))
    trace_context_rows = read_csv(config.path("trace_liquidity_context"))
    reconciliation_rows = read_csv(config.path("buyback_source_reconciliation"))
    diagnostics_rows = read_csv(config.path("event_diagnostics"))
    triage_rows = read_csv(config.path("results_triage"))
    evidence_rows = read_csv(config.path("evidence_ledger"))
    coverage_rows = read_csv(config.path("coverage_qa"))
    announcement_operation_rows = read_csv(config.path("announcement_operation_summary"))
    if not panel_rows:
        raise OffrunError("Cannot write report from an empty offrun panel")
    fixture_build = all(
        row.get("source_family", "").startswith("fixture") for row in operation_rows
    )

    source_inventory = tables / "source_inventory.csv"
    if not source_inventory.exists():
        _source_inventory_fallback(config.repo_root, source_inventory)

    _write_timeline_svg(operation_rows, figures / "buyback_timeline.svg", fixture=fixture_build)
    _write_event_svg(summary_rows, figures / "targeted_bucket_event_windows.svg")
    _write_count_svg(
        evidence_rows,
        config.path("evidence_grade_figure"),
        field="evidence_grade",
        title="Evidence-grade summary",
    )
    _write_count_svg(
        diagnostics_rows,
        config.path("source_granularity_figure"),
        field="trace_diagnostic_status",
        title="TRACE diagnostic support summary",
    )
    _write_findings_report(
        config.path("findings_report"),
        operation_rows=operation_rows,
        trace_rows=trace_context_rows,
        triage_rows=triage_rows,
        coverage_rows=coverage_rows,
        diagnostics_rows=diagnostics_rows,
    )

    operation_count = len({row.get("operation_id", "") for row in operation_rows})
    panel_count = len(panel_rows)
    targeted_count = sum(1 for row in panel_rows if row.get("targeted_bucket") == "1")
    control_count = panel_count - targeted_count
    non_missing_trace = sum(1 for row in panel_rows if row.get("trace_turnover"))
    non_missing_dealer_position = sum(
        1 for row in panel_rows if row.get("net_positions_usd_millions")
    )
    non_missing_fails = sum(1 for row in panel_rows if row.get("dealer_fails_total_usd_millions"))
    diagnostic_ready = sum(
        1 for row in diagnostics_rows if row.get("trace_diagnostic_status") == "diagnostic_ready"
    )
    pretrend_warnings = sum(1 for row in diagnostics_rows if row.get("pretrend_warning") == "1")
    placebo_warnings = sum(1 for row in diagnostics_rows if row.get("placebo_warning") == "1")
    supportive_rows = sum(
        1 for row in triage_rows if row.get("claim_status") == "supportive_diagnostic"
    )
    mixed_rows = sum(1 for row in triage_rows if row.get("claim_status") == "mixed_diagnostic")
    trace_dealer_coverage = sum(
        1
        for row in coverage_rows
        if row.get("coverage_status") in {"trace_dealer_position", "trace_dealer_fails"}
    )
    compared_event_types = sum(
        1
        for row in announcement_operation_rows
        if row.get("announcement_trace_change") and row.get("operation_trace_change")
    )
    crosscheck_ready = sum(
        1
        for row in reconciliation_rows
        if row.get("source_reconciliation_status") == "treasurydirect_crosscheck_ready"
    )

    package_label = "fixture-backed smoke package" if fixture_build else "real-source package"
    build_note = (
        "synthetic; it is intended to verify source contracts, panel joins, claim-boundary "
        "checks, and report wiring before any real raw data are added"
        if fixture_build
        else "based on local public-source and sibling-project inputs. TRACE rows are public "
        "aggregate proxies and dealer rows are aggregate Primary Dealer Statistics context"
    )
    trace_source_note = _trace_source_note(trace_context_rows)

    fixture_note = (
        """## Fixture note

The included fixtures are intentionally tiny. They are not evidence about real
Treasury markets; they only exercise the offrun code paths and validation gates.
"""
        if fixture_build
        else f"""## Source note

The real build uses ignored local raw/imported data plus sibling outputs.
{trace_source_note}
Dealer context uses bucket-mapped aggregate primary-dealer net positions plus
aggregate Treasury financing and fails series repeated across analysis buckets.
"""
    )

    text = f"""# offrun accounting report

This {package_label} provides **descriptive market-liquidity evidence**
around Treasury buyback announcement and operation windows. The current build is
{build_note}.

## Package summary

- Buyback operations: {operation_count}
- Offrun event-window rows: {panel_count}
- Targeted-bucket rows: {targeted_count}
- Nearby-control rows: {control_count}
- Rows with TRACE aggregate turnover proxy: {non_missing_trace}
- Rows with dealer net-position diagnostic: {non_missing_dealer_position}
- Rows with dealer fails diagnostic: {non_missing_fails}
- Event diagnostics ready for targeted-versus-control TRACE review: {diagnostic_ready}
- Event diagnostics with pretrend warnings: {pretrend_warnings}
- Event diagnostics with placebo warnings: {placebo_warnings}
- Event windows with both TRACE and dealer-position coverage: {trace_dealer_coverage}
- Operation/event pairs with both announcement and operation TRACE changes: {compared_event_types}
- Buyback operations with TreasuryDirect announcement/results link cross-checks: {crosscheck_ready}
- Supportive diagnostic rows: {supportive_rows}
- Mixed diagnostic rows: {mixed_rows}

## Diagnostic surfaces

- `output/tables/coverage_qa.csv` reports proxy coverage by operation and event type.
- `output/tables/buyback_source_reconciliation.csv` records whether buyback rows have
  FiscalData operation records and TreasuryDirect announcement/results links.
- `output/tables/event_diagnostics.csv` reports targeted-bucket changes, nearby-control
  changes, targeted-minus-control differences, and pretrend warnings.
- `output/tables/results_triage.csv` ranks diagnostic rows and assigns descriptive
  claim-status labels.
- `output/tables/pretrend_diagnostics.csv` and `output/tables/placebo_diagnostics.csv`
  separate pre-event drift checks from post-event descriptive readouts.
- `output/tables/evidence_ledger.csv` assigns source-limited evidence grades.
- `output/tables/dealer_source_granularity_audit.csv` records which dealer proxies
  are maturity-bucketed and which are aggregate context.
- `output/tables/announcement_operation_summary.csv` compares announcement-window and
  operation-window changes for each completed buyback operation.
- `output/tables/trace_source_granularity_audit.csv` records whether public TRACE
  source granularity can support better target-bucket or on/off-run diagnostics.
- Buyback intensity is accepted amount scaled by sibling outstanding stock when the
  `tdcladder` denominator is available. Alternative denominators scale accepted
  amount by liquidity-weighted sibling supply and same-window TRACE volume when
  those fields are available.

## Interpretation boundary

The evidence package is descriptive. Public aggregate TRACE statistics are treated
as broad volume or turnover proxies, not transaction-level or CUSIP-level
liquidity evidence. Primary Dealer Statistics are aggregate dealer-sector
diagnostics for positions, financing, and settlement fails.

Treasury buyback target selection may reflect existing market conditions. Any
production use should pair post-operation windows with pre-trend checks,
announcement-versus-operation timing, and targeted-bucket versus nearby-bucket
comparisons.

## Generated artifacts

- `data/derived/offrun_panel.csv`
- `output/tables/buyback_event_summary.csv`
- `output/tables/buyback_source_reconciliation.csv`
- `output/tables/event_diagnostics.csv`
- `output/tables/results_triage.csv`
- `output/tables/pretrend_diagnostics.csv`
- `output/tables/placebo_diagnostics.csv`
- `output/tables/evidence_ledger.csv`
- `output/tables/dealer_source_granularity_audit.csv`
- `output/tables/coverage_qa.csv`
- `output/tables/announcement_operation_summary.csv`
- `output/tables/trace_source_granularity_audit.csv`
- `output/tables/source_inventory.csv`
- `output/figures/buyback_timeline.svg`
- `output/figures/targeted_bucket_event_windows.svg`
- `output/figures/evidence_grade_summary.svg`
- `output/figures/source_granularity_summary.svg`
- `output/reports/offrun_findings_report.md`

{fixture_note}
"""
    write_text(report_file, text)
    return report_file
