"""Command line interface for offrun."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import validate_config
from .contracts import copy_sibling_outputs, validate_sibling_sources
from .io import OffrunError
from .manifests import write_output_manifest
from .panels import (
    build_buyback_operations_panel,
    build_liquidity_context_panel,
    build_offrun_panel,
)
from .real_sources import download_fiscaldata_buybacks, prepare_real_inputs
from .reports import write_offrun_report
from .validation import validate_offrun_package


def _repo_root(args: argparse.Namespace) -> Path | None:
    return Path(args.repo_root) if args.repo_root is not None else None


def _print_lines(lines: Sequence[str]) -> None:
    for line in lines:
        print(line)


def _cmd_validate_config(args: argparse.Namespace) -> int:
    _print_lines(validate_config(_repo_root(args)))
    return 0


def _cmd_validate_sibling_sources(args: argparse.Namespace) -> int:
    statuses = validate_sibling_sources(
        args.sibling_root,
        repo_root=_repo_root(args),
        strict=args.strict,
    )
    for status in statuses:
        required = "required" if status.required else "optional"
        state = "ok" if status.ok else "missing_or_incomplete"
        print(f"{status.sibling}:{status.artifact} [{required}] {state} rows={status.row_count}")
    return 0


def _cmd_copy_sibling_outputs(args: argparse.Namespace) -> int:
    copied = copy_sibling_outputs(
        args.sibling_root,
        repo_root=_repo_root(args),
        overwrite=args.overwrite,
        strict=args.strict,
    )
    if copied:
        for path in copied:
            print(f"copied {path}")
    else:
        print("no sibling artifacts copied")
    return 0


def _cmd_build_buybacks(args: argparse.Namespace) -> int:
    operations, calendar = build_buyback_operations_panel(
        _repo_root(args),
        input_path=args.input,
        output_path=args.output,
        event_calendar_output=args.event_calendar_output,
    )
    print(f"wrote {operations}")
    print(f"wrote {calendar}")
    return 0


def _cmd_build_liquidity(args: argparse.Namespace) -> int:
    trace, dealer, panel = build_liquidity_context_panel(
        _repo_root(args),
        trace_input=args.trace_input,
        dealer_input=args.dealer_input,
        output_path=args.output,
        trace_output=args.trace_output,
        dealer_output=args.dealer_output,
    )
    print(f"wrote {trace}")
    print(f"wrote {dealer}")
    print(f"wrote {panel}")
    return 0


def _cmd_build_offrun(args: argparse.Namespace) -> int:
    panel, summary = build_offrun_panel(
        _repo_root(args),
        buyback_panel_path=args.buybacks,
        event_calendar_path=args.event_calendar,
        liquidity_context_path=args.liquidity_context,
        output_path=args.output,
        summary_output=args.summary_output,
    )
    print(f"wrote {panel}")
    print(f"wrote {summary}")
    return 0


def _cmd_write_report(args: argparse.Namespace) -> int:
    path = write_offrun_report(
        _repo_root(args),
        panel_path=args.panel,
        summary_path=args.summary,
        output_md=args.output_md,
        figure_dir=args.figure_dir,
        table_dir=args.table_dir,
    )
    print(f"wrote {path}")
    return 0


def _cmd_write_manifest(args: argparse.Namespace) -> int:
    path = write_output_manifest(_repo_root(args), output_path=args.output)
    print(f"wrote {path}")
    return 0


def _cmd_validate_package(args: argparse.Namespace) -> int:
    _print_lines(validate_offrun_package(_repo_root(args), strict=args.strict))
    return 0


def _cmd_download_buybacks(args: argparse.Namespace) -> int:
    path = download_fiscaldata_buybacks(_repo_root(args), output_path=args.output)
    print(f"wrote {path}")
    return 0


def _cmd_prepare_real_inputs(args: argparse.Namespace) -> int:
    paths = prepare_real_inputs(
        _repo_root(args),
        sibling_root=args.sibling_root,
        buybacks_input=args.buybacks_input,
        download_buybacks=args.download_buybacks,
    )
    for path in paths:
        print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser."""

    parser = argparse.ArgumentParser(
        prog="offrun",
        description="Treasury buybacks and off-the-run liquidity evidence package.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root. Defaults to the current working tree.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-config")
    validate_parser.set_defaults(func=_cmd_validate_config)

    sibling_parser = subparsers.add_parser("validate-sibling-sources")
    sibling_parser.add_argument("--sibling-root", required=True)
    sibling_parser.add_argument("--strict", action="store_true")
    sibling_parser.set_defaults(func=_cmd_validate_sibling_sources)

    copy_parser = subparsers.add_parser("copy-sibling-outputs")
    copy_parser.add_argument("--sibling-root", required=True)
    copy_parser.add_argument("--overwrite", action="store_true")
    copy_parser.add_argument("--strict", action="store_true")
    copy_parser.set_defaults(func=_cmd_copy_sibling_outputs)

    buybacks_parser = subparsers.add_parser("build-buyback-operations-panel")
    buybacks_parser.add_argument("--input", default=None)
    buybacks_parser.add_argument("--output", default=None)
    buybacks_parser.add_argument("--event-calendar-output", default=None)
    buybacks_parser.set_defaults(func=_cmd_build_buybacks)

    liquidity_parser = subparsers.add_parser("build-liquidity-context-panel")
    liquidity_parser.add_argument("--trace-input", default=None)
    liquidity_parser.add_argument("--dealer-input", default=None)
    liquidity_parser.add_argument("--output", default=None)
    liquidity_parser.add_argument("--trace-output", default=None)
    liquidity_parser.add_argument("--dealer-output", default=None)
    liquidity_parser.set_defaults(func=_cmd_build_liquidity)

    offrun_parser = subparsers.add_parser("build-offrun-panel")
    offrun_parser.add_argument("--buybacks", default=None)
    offrun_parser.add_argument("--event-calendar", default=None)
    offrun_parser.add_argument("--liquidity-context", default=None)
    offrun_parser.add_argument("--output", default=None)
    offrun_parser.add_argument("--summary-output", default=None)
    offrun_parser.set_defaults(func=_cmd_build_offrun)

    report_parser = subparsers.add_parser("write-offrun-report")
    report_parser.add_argument("--panel", default=None)
    report_parser.add_argument("--summary", default=None)
    report_parser.add_argument("--output-md", default=None)
    report_parser.add_argument("--figure-dir", default=None)
    report_parser.add_argument("--table-dir", default=None)
    report_parser.set_defaults(func=_cmd_write_report)

    manifest_parser = subparsers.add_parser("write-output-manifest")
    manifest_parser.add_argument("--output", default=None)
    manifest_parser.set_defaults(func=_cmd_write_manifest)

    package_parser = subparsers.add_parser("validate-offrun-package")
    package_parser.add_argument("--strict", action="store_true")
    package_parser.set_defaults(func=_cmd_validate_package)

    download_parser = subparsers.add_parser("download-fiscaldata-buybacks")
    download_parser.add_argument("--output", default=None)
    download_parser.set_defaults(func=_cmd_download_buybacks)

    real_parser = subparsers.add_parser("prepare-real-inputs")
    real_parser.add_argument("--sibling-root", default="..")
    real_parser.add_argument("--buybacks-input", default=None)
    real_parser.add_argument("--download-buybacks", action="store_true")
    real_parser.set_defaults(func=_cmd_prepare_real_inputs)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except OffrunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
