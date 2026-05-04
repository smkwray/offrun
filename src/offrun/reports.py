"""Report and figure generation."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .config import load_config
from .io import OffrunError, as_float, read_csv, write_csv, write_text


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


def _write_timeline_svg(rows: list[dict[str, str]], output_path: Path) -> None:
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
        "Synthetic buyback operation timeline</text>",
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
    if not panel_rows:
        raise OffrunError("Cannot write report from an empty offrun panel")

    source_inventory = tables / "source_inventory.csv"
    if not source_inventory.exists():
        _source_inventory_fallback(config.repo_root, source_inventory)

    _write_timeline_svg(operation_rows, figures / "buyback_timeline.svg")
    _write_event_svg(summary_rows, figures / "targeted_bucket_event_windows.svg")

    operation_count = len({row.get("operation_id", "") for row in operation_rows})
    panel_count = len(panel_rows)
    targeted_count = sum(1 for row in panel_rows if row.get("targeted_bucket") == "1")
    control_count = panel_count - targeted_count
    non_missing_trace = sum(1 for row in panel_rows if row.get("trace_turnover"))
    non_missing_fails = sum(1 for row in panel_rows if row.get("dealer_fails_total_usd_millions"))

    text = f"""# offrun accounting report

This fixture-backed starter package provides **descriptive market-liquidity evidence**
around Treasury buyback announcement and operation windows. The current build is
synthetic and is intended to verify source contracts, panel joins, claim-boundary
checks, and report wiring before any real raw data are added.

## Package summary

- Buyback operations: {operation_count}
- Offrun event-window rows: {panel_count}
- Targeted-bucket rows: {targeted_count}
- Nearby-control rows: {control_count}
- Rows with TRACE aggregate turnover proxy: {non_missing_trace}
- Rows with dealer fails diagnostic: {non_missing_fails}

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
- `output/tables/source_inventory.csv`
- `output/figures/buyback_timeline.svg`
- `output/figures/targeted_bucket_event_windows.svg`

## Fixture note

The included fixtures are intentionally tiny. They are not evidence about real
Treasury markets; they only exercise the offrun code paths and validation gates.
"""
    write_text(report_file, text)
    return report_file
