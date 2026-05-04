"""TRACE public-source granularity audit."""

from __future__ import annotations

from pathlib import Path

from .config import load_config
from .io import read_csv, write_csv

AUDIT_FIELDS = [
    "source_surface",
    "frequency",
    "first_available",
    "security_scope",
    "remaining_maturity_detail",
    "on_off_run_detail",
    "volume_fields",
    "price_fields",
    "package_use",
    "claim_boundary",
    "upgrade_action",
]


def _tdcladder_trace_row(sibling_root: Path | str) -> dict[str, str]:
    source = (
        Path(sibling_root).resolve()
        / "tdcladder/data/raw/market_liquidity/turnover_by_maturity.csv"
    )
    if not source.exists():
        return {
            "source_surface": "tdcladder reused TRACE turnover",
            "frequency": "not available",
            "first_available": "",
            "security_scope": "source file missing",
            "remaining_maturity_detail": "not verified",
            "on_off_run_detail": "not verified",
            "volume_fields": "",
            "price_fields": "",
            "package_use": "missing current fallback input",
            "claim_boundary": "cannot support offrun TRACE diagnostics until source exists",
            "upgrade_action": "refresh tdcladder or provide a direct FINRA aggregate extract",
        }
    rows = read_csv(source)
    months = sorted({row.get("month", "") for row in rows if row.get("month")})
    granularities = sorted(
        {row.get("source_granularity", "") for row in rows if row.get("source_granularity")}
    )
    maturity_values = sorted(
        {row.get("maturity_bucket", "") for row in rows if row.get("maturity_bucket")}
    )
    security_types = sorted(
        {row.get("security_type", "") for row in rows if row.get("security_type")}
    )
    has_maturity_detail = any(value not in {"", "all"} for value in maturity_values)
    return {
        "source_surface": "tdcladder reused TRACE turnover",
        "frequency": ", ".join(granularities) or "monthly",
        "first_available": months[0] if months else "",
        "security_scope": "; ".join(security_types),
        "remaining_maturity_detail": "yes" if has_maturity_detail else "no",
        "on_off_run_detail": "no",
        "volume_fields": "trace_volume; trace_trade_count; outstanding_amount; turnover",
        "price_fields": "none",
        "package_use": "current real-package fallback; normalized into repeated analysis buckets",
        "claim_boundary": "broad aggregate turnover only; not target-bucket or CUSIP liquidity",
        "upgrade_action": (
            "replace or augment with FINRA daily/monthly aggregate files when available"
        ),
    }


def audit_trace_source_granularity(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
    output_path: Path | str | None = None,
) -> Path:
    """Write a reproducible audit of public TRACE source granularity.

    The audit distinguishes the current reused ``tdcladder`` turnover fallback from
    the newer FINRA public daily/monthly aggregate surfaces. It records that FINRA
    advertises remaining-maturity and on/off-run groupings for Nominal Coupons and
    TIPS, but keeps the package claim boundary descriptive because the public file
    is still aggregate rather than CUSIP-level or transaction-level.
    """

    config = load_config(repo_root)
    output = (
        Path(output_path)
        if output_path is not None
        else config.path("trace_source_granularity_audit")
    )
    rows = [
        _tdcladder_trace_row(sibling_root),
        {
            "source_surface": "FINRA Treasury Daily Aggregate Statistics",
            "frequency": "daily",
            "first_available": "2023-02-13",
            "security_scope": "Bills; FRN; Nominal Coupons; TIPS",
            "remaining_maturity_detail": "yes for Nominal Coupons and TIPS",
            "on_off_run_detail": "yes for Nominal Coupons and TIPS",
            "volume_fields": "volume; trade counts; ATS/interdealer; dealer-to-customer; total",
            "price_fields": "VWAP for on-the-run nominal coupons",
            "package_use": "candidate upgrade for target-bucket and on/off-run volume diagnostics",
            "claim_boundary": (
                "aggregate public data; not CUSIP-level or transaction-level liquidity"
            ),
            "upgrade_action": (
                "add direct FINRA aggregate-file ingestion before promoting target-bucket claims"
            ),
        },
        {
            "source_surface": "FINRA Treasury Monthly Aggregate Statistics",
            "frequency": "monthly file with daily observations for the prior month",
            "first_available": "2023-02",
            "security_scope": "Bills; FRN; Nominal Coupons; TIPS",
            "remaining_maturity_detail": "yes for Nominal Coupons and TIPS",
            "on_off_run_detail": "yes for Nominal Coupons and TIPS",
            "volume_fields": "volume; trade counts; ATS/interdealer; dealer-to-customer; total",
            "price_fields": "on-the-run nominal coupon price fields where reported",
            "package_use": "candidate lower-friction bulk source for offrun real-package extension",
            "claim_boundary": "aggregate public data; useful for volume/turnover context only",
            "upgrade_action": (
                "prefer monthly files for bulk backfill if API or file export is stable"
            ),
        },
    ]
    write_csv(output, rows, AUDIT_FIELDS)
    return output
