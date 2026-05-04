"""Panel builders for buyback operations and liquidity context."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from .config import OffrunConfig, load_config
from .io import OffrunError, as_float, format_number, read_csv, write_csv
from .periods import business_day_window, month_key, parse_date


def _resolve_input(
    repo_root: Path,
    configured: str,
    fixture: str,
    explicit: Path | str | None,
) -> Path:
    if explicit is not None:
        return Path(explicit)
    configured_path = repo_root / configured
    if configured_path.exists():
        return configured_path
    fixture_path = repo_root / fixture
    if fixture_path.exists():
        return fixture_path
    return configured_path


def _output_path(config: OffrunConfig, key: str, explicit: Path | str | None) -> Path:
    return Path(explicit) if explicit is not None else config.path(key)


def _schema_fields(config: OffrunConfig, dataset: str) -> list[str]:
    datasets = config.schemas.get("datasets", {})
    dataset_payload = datasets.get(dataset, {}) if isinstance(datasets, Mapping) else {}
    fields = (
        dataset_payload.get("required_columns", [])
        if isinstance(dataset_payload, Mapping)
        else []
    )
    return [str(field) for field in fields]


def _bucket_order(config: OffrunConfig) -> list[str]:
    buckets = config.variables.get("maturity_buckets", {})
    if not isinstance(buckets, Mapping):
        return []
    return [str(bucket) for bucket in buckets.get("order", [])]


def _nearby_control_buckets(config: OffrunConfig, bucket: str) -> list[str]:
    buckets = config.variables.get("maturity_buckets", {})
    if not isinstance(buckets, Mapping):
        return []
    nearby = buckets.get("nearby_control_buckets", {})
    if not isinstance(nearby, Mapping):
        return []
    return [str(control) for control in nearby.get(bucket, [])]


def _daily_window_bounds(config: OffrunConfig) -> tuple[int, int]:
    event_windows = config.variables.get("event_windows", {})
    if not isinstance(event_windows, Mapping):
        return 10, 20
    daily = event_windows.get("daily_business_days", {})
    if not isinstance(daily, Mapping):
        return 10, 20
    return int(daily.get("pre", 10)), int(daily.get("post", 20))


def build_buyback_operations_panel(
    repo_root: Path | str | None = None,
    *,
    input_path: Path | str | None = None,
    output_path: Path | str | None = None,
    event_calendar_output: Path | str | None = None,
) -> tuple[Path, Path]:
    """Build normalized buyback operations and event-calendar panels."""

    config = load_config(repo_root)
    input_file = _resolve_input(
        config.repo_root,
        "data/imported/buybacks/buyback_operations.csv",
        "tests/fixtures/buybacks/buyback_operations_fixture.csv",
        input_path,
    )
    operation_output = _output_path(config, "buyback_operations", output_path)
    calendar_output = _output_path(config, "buyback_event_calendar", event_calendar_output)

    raw_rows = read_csv(input_file)
    bucket_order = set(_bucket_order(config))
    operation_rows: list[dict[str, str]] = []
    calendar_rows: list[dict[str, str]] = []
    pre, post = _daily_window_bounds(config)

    for index, row in enumerate(raw_rows, start=1):
        operation_id = row.get("operation_id", "").strip() or f"buyback_{index:04d}"
        maturity_bucket = row.get("maturity_bucket", "").strip()
        if bucket_order and maturity_bucket not in bucket_order:
            raise OffrunError(f"Unknown maturity bucket {maturity_bucket!r} in {input_file}")
        offered = as_float(row.get("offered_amount_usd_millions"))
        accepted = as_float(row.get("accepted_amount_usd_millions"))
        acceptance_ratio = accepted / offered if offered else 0.0
        operation_row = {
            "operation_id": operation_id,
            "announcement_date": row.get("announcement_date", "").strip(),
            "operation_date": row.get("operation_date", "").strip(),
            "security_type": row.get("security_type", "").strip(),
            "maturity_bucket": maturity_bucket,
            "offered_amount_usd_millions": format_number(offered),
            "accepted_amount_usd_millions": format_number(accepted),
            "acceptance_ratio": format_number(acceptance_ratio),
            "operation_purpose": row.get("operation_purpose", "").strip(),
            "source_family": row.get("source_family", "fixture").strip() or "fixture",
        }
        operation_rows.append(operation_row)

        for event_type, date_key in (
            ("announcement", "announcement_date"),
            ("operation", "operation_date"),
        ):
            event_date_text = operation_row.get(date_key, "")
            if not event_date_text:
                continue
            event_date = parse_date(event_date_text)
            for event_day, window_date in business_day_window(event_date, pre, post):
                calendar_rows.append(
                    {
                        "operation_id": operation_id,
                        "event_type": event_type,
                        "event_date": event_date.isoformat(),
                        "window_date": window_date.isoformat(),
                        "event_day": str(event_day),
                        "maturity_bucket": maturity_bucket,
                        "security_type": operation_row["security_type"],
                        "accepted_amount_usd_millions": operation_row[
                            "accepted_amount_usd_millions"
                        ],
                        "offered_amount_usd_millions": operation_row[
                            "offered_amount_usd_millions"
                        ],
                        "acceptance_ratio": operation_row["acceptance_ratio"],
                        "targeted_bucket": "1",
                    }
                )

    operation_fields = [
        "operation_id",
        "announcement_date",
        "operation_date",
        "security_type",
        "maturity_bucket",
        "offered_amount_usd_millions",
        "accepted_amount_usd_millions",
        "acceptance_ratio",
        "operation_purpose",
        "source_family",
    ]
    calendar_fields = _schema_fields(config, "buyback_event_calendar") + [
        "security_type",
        "accepted_amount_usd_millions",
        "offered_amount_usd_millions",
        "acceptance_ratio",
    ]
    write_csv(operation_output, operation_rows, operation_fields)
    write_csv(calendar_output, calendar_rows, calendar_fields)
    return operation_output, calendar_output


def _load_maturity_context(config: OffrunConfig) -> dict[tuple[str, str], dict[str, str]]:
    path = config.repo_root / "data/imported/tdcladder/monthly_ladder_panel.csv"
    if not path.exists():
        return {}
    context: dict[tuple[str, str], dict[str, str]] = {}
    for row in read_csv(path):
        date_text = row.get("date", "")
        bucket = row.get("maturity_bucket", "")
        if not date_text or not bucket:
            continue
        context[(month_key(date_text), bucket)] = {
            "sibling_outstanding_usd_millions": row.get("outstanding_usd_millions", ""),
            "sibling_liquidity_weight": row.get("liquidity_weight", ""),
        }
    return context


def build_liquidity_context_panel(
    repo_root: Path | str | None = None,
    *,
    trace_input: Path | str | None = None,
    dealer_input: Path | str | None = None,
    output_path: Path | str | None = None,
    trace_output: Path | str | None = None,
    dealer_output: Path | str | None = None,
) -> tuple[Path, Path, Path]:
    """Build TRACE, dealer, and merged liquidity context panels."""

    config = load_config(repo_root)
    trace_file = _resolve_input(
        config.repo_root,
        "data/imported/trace/trace_treasury_aggregates.csv",
        "tests/fixtures/trace/trace_aggregate_fixture.csv",
        trace_input,
    )
    dealer_file = _resolve_input(
        config.repo_root,
        "data/imported/dealer/primary_dealer_statistics.csv",
        "tests/fixtures/dealer/primary_dealer_fixture.csv",
        dealer_input,
    )
    panel_output = _output_path(config, "liquidity_context_panel", output_path)
    trace_context_output = _output_path(config, "trace_liquidity_context", trace_output)
    dealer_context_output = _output_path(config, "dealer_liquidity_context", dealer_output)

    trace_rows: list[dict[str, str]] = []
    context: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in read_csv(trace_file):
        trading_volume = as_float(row.get("trading_volume_usd_millions"))
        outstanding = as_float(row.get("outstanding_usd_millions"))
        turnover = trading_volume / outstanding if outstanding else 0.0
        normalized = {
            "date": row.get("date", "").strip(),
            "maturity_bucket": row.get("maturity_bucket", "").strip(),
            "trace_category": row.get("trace_category", "aggregate_public").strip(),
            "trading_volume_usd_millions": format_number(trading_volume),
            "outstanding_usd_millions": format_number(outstanding),
            "trace_turnover": format_number(turnover),
            "source_family": row.get("source_family", "fixture_trace").strip() or "fixture_trace",
        }
        trace_rows.append(normalized)
        key = (normalized["date"], normalized["maturity_bucket"])
        context[key].update(normalized)

    dealer_rows: list[dict[str, str]] = []
    for row in read_csv(dealer_file):
        fails_deliver = as_float(row.get("fails_to_deliver_usd_millions"))
        fails_receive = as_float(row.get("fails_to_receive_usd_millions"))
        fails_total = fails_deliver + fails_receive
        normalized = {
            "date": row.get("date", "").strip(),
            "maturity_bucket": row.get("maturity_bucket", "").strip(),
            "dealer_category": row.get("dealer_category", "treasury").strip(),
            "net_positions_usd_millions": format_number(
                as_float(row.get("net_positions_usd_millions"))
            ),
            "financing_usd_millions": format_number(as_float(row.get("financing_usd_millions"))),
            "fails_to_deliver_usd_millions": format_number(fails_deliver),
            "fails_to_receive_usd_millions": format_number(fails_receive),
            "dealer_fails_total_usd_millions": format_number(fails_total),
            "source_family": row.get("source_family", "fixture_dealer").strip() or "fixture_dealer",
        }
        dealer_rows.append(normalized)
        key = (normalized["date"], normalized["maturity_bucket"])
        context[key].update(normalized)

    maturity_context = _load_maturity_context(config)
    panel_rows: list[dict[str, str]] = []
    for date_text, maturity_bucket in sorted(context):
        row = dict(context[(date_text, maturity_bucket)])
        sibling = maturity_context.get((month_key(date_text), maturity_bucket), {})
        proxy_fields = [
            "trading_volume_usd_millions",
            "trace_turnover",
            "net_positions_usd_millions",
            "financing_usd_millions",
            "dealer_fails_total_usd_millions",
        ]
        proxy_count = sum(1 for field in proxy_fields if row.get(field) not in (None, ""))
        panel_rows.append(
            {
                "date": date_text,
                "maturity_bucket": maturity_bucket,
                "trading_volume_usd_millions": row.get("trading_volume_usd_millions", ""),
                "outstanding_usd_millions": row.get("outstanding_usd_millions", ""),
                "trace_turnover": row.get("trace_turnover", ""),
                "net_positions_usd_millions": row.get("net_positions_usd_millions", ""),
                "financing_usd_millions": row.get("financing_usd_millions", ""),
                "dealer_fails_total_usd_millions": row.get(
                    "dealer_fails_total_usd_millions",
                    "",
                ),
                "sibling_outstanding_usd_millions": sibling.get(
                    "sibling_outstanding_usd_millions",
                    "",
                ),
                "sibling_liquidity_weight": sibling.get("sibling_liquidity_weight", ""),
                "liquidity_proxy_count": str(proxy_count),
            }
        )

    trace_fields = _schema_fields(config, "trace_liquidity_context") + ["source_family"]
    dealer_fields = _schema_fields(config, "dealer_liquidity_context") + ["source_family"]
    panel_fields = _schema_fields(config, "liquidity_context_panel") + [
        "outstanding_usd_millions",
        "sibling_outstanding_usd_millions",
        "sibling_liquidity_weight",
    ]
    write_csv(trace_context_output, trace_rows, trace_fields)
    write_csv(dealer_context_output, dealer_rows, dealer_fields)
    write_csv(panel_output, panel_rows, panel_fields)
    return trace_context_output, dealer_context_output, panel_output


def _context_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row.get("date", ""), row.get("maturity_bucket", "")): row for row in rows}


def _build_panel_row(
    event_row: Mapping[str, str],
    comparison_bucket: str,
    targeted_bucket: bool,
    context_row: Mapping[str, str] | None,
) -> dict[str, str]:
    context = context_row or {}
    return {
        "operation_id": event_row.get("operation_id", ""),
        "event_type": event_row.get("event_type", ""),
        "event_day": event_row.get("event_day", ""),
        "event_date": event_row.get("event_date", ""),
        "window_date": event_row.get("window_date", ""),
        "target_maturity_bucket": event_row.get("maturity_bucket", ""),
        "comparison_maturity_bucket": comparison_bucket,
        "targeted_bucket": "1" if targeted_bucket else "0",
        "security_type": event_row.get("security_type", ""),
        "accepted_amount_usd_millions": event_row.get("accepted_amount_usd_millions", ""),
        "offered_amount_usd_millions": event_row.get("offered_amount_usd_millions", ""),
        "acceptance_ratio": event_row.get("acceptance_ratio", ""),
        "trading_volume_usd_millions": context.get("trading_volume_usd_millions", ""),
        "trace_turnover": context.get("trace_turnover", ""),
        "net_positions_usd_millions": context.get("net_positions_usd_millions", ""),
        "financing_usd_millions": context.get("financing_usd_millions", ""),
        "dealer_fails_total_usd_millions": context.get("dealer_fails_total_usd_millions", ""),
        "liquidity_proxy_count": context.get("liquidity_proxy_count", "0"),
    }


def _mean(values: list[float]) -> float | None:
    non_missing = [value for value in values if value == value]
    if not non_missing:
        return None
    return sum(non_missing) / len(non_missing)


def _summary_rows(panel_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in panel_rows:
        key = (
            row["operation_id"],
            row["event_type"],
            row["comparison_maturity_bucket"],
            row["targeted_bucket"],
        )
        grouped[key].append(row)

    summary: list[dict[str, str]] = []
    for (
        _operation_id,
        _event_type,
        _comparison_bucket,
        _targeted,
    ), rows in sorted(grouped.items()):
        pre_turnover = [
            as_float(row.get("trace_turnover"), default=float("nan"))
            for row in rows
            if as_float(row.get("event_day")) < 0 and row.get("trace_turnover")
        ]
        post_turnover = [
            as_float(row.get("trace_turnover"), default=float("nan"))
            for row in rows
            if as_float(row.get("event_day")) > 0 and row.get("trace_turnover")
        ]
        pre_fails = [
            as_float(row.get("dealer_fails_total_usd_millions"), default=float("nan"))
            for row in rows
            if as_float(row.get("event_day")) < 0 and row.get("dealer_fails_total_usd_millions")
        ]
        post_fails = [
            as_float(row.get("dealer_fails_total_usd_millions"), default=float("nan"))
            for row in rows
            if as_float(row.get("event_day")) > 0 and row.get("dealer_fails_total_usd_millions")
        ]
        pre_turnover_mean = _mean(pre_turnover)
        post_turnover_mean = _mean(post_turnover)
        pre_fails_mean = _mean(pre_fails)
        post_fails_mean = _mean(post_fails)
        first = rows[0]
        summary.append(
            {
                "operation_id": first["operation_id"],
                "event_type": first["event_type"],
                "target_maturity_bucket": first["target_maturity_bucket"],
                "comparison_maturity_bucket": first["comparison_maturity_bucket"],
                "targeted_bucket": first["targeted_bucket"],
                "pre_event_trace_turnover_mean": format_number(pre_turnover_mean),
                "post_event_trace_turnover_mean": format_number(post_turnover_mean),
                "post_minus_pre_trace_turnover": format_number(
                    None
                    if pre_turnover_mean is None or post_turnover_mean is None
                    else post_turnover_mean - pre_turnover_mean
                ),
                "pre_event_fails_mean": format_number(pre_fails_mean),
                "post_event_fails_mean": format_number(post_fails_mean),
                "post_minus_pre_fails": format_number(
                    None
                    if pre_fails_mean is None or post_fails_mean is None
                    else post_fails_mean - pre_fails_mean
                ),
                "event_window_rows": str(len(rows)),
            }
        )
    return summary


def build_offrun_panel(
    repo_root: Path | str | None = None,
    *,
    buyback_panel_path: Path | str | None = None,
    event_calendar_path: Path | str | None = None,
    liquidity_context_path: Path | str | None = None,
    output_path: Path | str | None = None,
    summary_output: Path | str | None = None,
) -> tuple[Path, Path]:
    """Build the merged event-window offrun panel and summary table."""

    config = load_config(repo_root)
    buyback_file = _output_path(config, "buyback_operations", buyback_panel_path)
    event_file = _output_path(config, "buyback_event_calendar", event_calendar_path)
    liquidity_file = _output_path(config, "liquidity_context_panel", liquidity_context_path)
    panel_output = _output_path(config, "offrun_panel", output_path)
    summary_file = _output_path(config, "buyback_event_summary", summary_output)

    if not buyback_file.exists():
        raise OffrunError(f"Buyback operations panel missing: {buyback_file}")
    events = read_csv(event_file)
    context = _context_index(read_csv(liquidity_file))

    panel_rows: list[dict[str, str]] = []
    for event_row in events:
        target_bucket = event_row.get("maturity_bucket", "")
        window_date = event_row.get("window_date", "")
        panel_rows.append(
            _build_panel_row(
                event_row,
                target_bucket,
                True,
                context.get((window_date, target_bucket)),
            )
        )
        for control_bucket in _nearby_control_buckets(config, target_bucket):
            panel_rows.append(
                _build_panel_row(
                    event_row,
                    control_bucket,
                    False,
                    context.get((window_date, control_bucket)),
                )
            )

    panel_fields = _schema_fields(config, "offrun_panel") + [
        "event_date",
        "security_type",
        "offered_amount_usd_millions",
        "acceptance_ratio",
        "trading_volume_usd_millions",
        "net_positions_usd_millions",
        "financing_usd_millions",
        "liquidity_proxy_count",
    ]
    summary_fields = _schema_fields(config, "buyback_event_summary") + ["event_window_rows"]
    write_csv(panel_output, panel_rows, panel_fields)
    write_csv(summary_file, _summary_rows(panel_rows), summary_fields)
    return panel_output, summary_file
