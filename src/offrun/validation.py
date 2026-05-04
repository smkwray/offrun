"""Validation gates for outputs and claim-boundary language."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import load_config, validate_config
from .io import OffrunError, count_csv_rows, read_csv, read_text


class ValidationError(OffrunError):
    """Raised when package validation fails."""


def _claim_boundary(config_payload: Mapping[str, Any]) -> Mapping[str, Any]:
    claim = config_payload.get("claim_boundary", {})
    if not isinstance(claim, Mapping):
        return {}
    return claim


def validate_claim_language(text: str, config_payload: Mapping[str, Any]) -> list[str]:
    """Validate report language against configured claim boundaries."""

    claim = _claim_boundary(config_payload)
    lowered = text.lower()
    failures: list[str] = []
    for phrase in claim.get("required_report_phrases", []):
        if str(phrase).lower() not in lowered:
            failures.append(f"missing required phrase: {phrase}")
    for phrase in claim.get("forbidden_unqualified_phrases", []):
        if str(phrase).lower() in lowered:
            failures.append(f"forbidden unqualified phrase found: {phrase}")
    return failures


def _require_existing(path: Path, failures: list[str]) -> None:
    if not path.exists():
        failures.append(f"missing required output: {path}")


def _validate_csv_rows(path: Path, failures: list[str], *, min_rows: int = 1) -> None:
    if path.exists() and count_csv_rows(path) < min_rows:
        failures.append(f"CSV output has fewer than {min_rows} rows: {path}")


def _validate_panel_columns(path: Path, required_columns: list[str], failures: list[str]) -> None:
    if not path.exists():
        return
    rows = read_csv(path)
    if not rows:
        return
    header = set(rows[0])
    missing = sorted(set(required_columns).difference(header))
    if missing:
        failures.append(f"{path} missing columns: {', '.join(missing)}")


def validate_offrun_package(
    repo_root: Path | str | None = None,
    *,
    strict: bool = False,
) -> list[str]:
    """Validate generated package artifacts and claim-boundary language."""

    config = load_config(repo_root)
    messages = validate_config(config.repo_root)
    failures: list[str] = []

    output_keys = [
        "buyback_operations",
        "buyback_event_calendar",
        "liquidity_context_panel",
        "offrun_panel",
        "buyback_event_summary",
        "event_diagnostics",
        "results_triage",
        "coverage_qa",
        "announcement_operation_summary",
        "trace_source_granularity_audit",
        "source_inventory",
        "report",
        "findings_report",
        "buyback_timeline_figure",
        "targeted_bucket_figure",
        "manifest",
    ]
    for key in output_keys:
        _require_existing(config.path(key), failures)

    for key in (
        "buyback_operations",
        "buyback_event_calendar",
        "liquidity_context_panel",
        "offrun_panel",
        "buyback_event_summary",
        "event_diagnostics",
        "results_triage",
        "coverage_qa",
        "announcement_operation_summary",
        "trace_source_granularity_audit",
    ):
        _validate_csv_rows(config.path(key), failures)

    datasets = config.schemas.get("datasets", {})
    if isinstance(datasets, Mapping):
        for dataset, key in (
            ("buyback_operations", "buyback_operations"),
            ("buyback_event_calendar", "buyback_event_calendar"),
            ("liquidity_context_panel", "liquidity_context_panel"),
            ("offrun_panel", "offrun_panel"),
            ("buyback_event_summary", "buyback_event_summary"),
            ("event_diagnostics", "event_diagnostics"),
            ("results_triage", "results_triage"),
            ("coverage_qa", "coverage_qa"),
            ("announcement_operation_summary", "announcement_operation_summary"),
            ("trace_source_granularity_audit", "trace_source_granularity_audit"),
        ):
            payload = datasets.get(dataset, {})
            if isinstance(payload, Mapping):
                required_columns = [str(col) for col in payload.get("required_columns", [])]
                _validate_panel_columns(config.path(key), required_columns, failures)

    report_path = config.path("report")
    if report_path.exists():
        failures.extend(validate_claim_language(read_text(report_path), config.project))
    findings_path = config.path("findings_report")
    if findings_path.exists():
        failures.extend(validate_claim_language(read_text(findings_path), config.project))

    if strict and failures:
        raise ValidationError("Package validation failed: " + "; ".join(failures))
    messages.extend(f"warning: {failure}" for failure in failures)
    if not failures:
        messages.append("offrun package outputs ok")
    return messages
