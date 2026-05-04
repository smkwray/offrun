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


def _optional_number(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    return format_number(as_float(text))


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
        fails_deliver_text = _optional_number(row.get("fails_to_deliver_usd_millions"))
        fails_receive_text = _optional_number(row.get("fails_to_receive_usd_millions"))
        fails_total = ""
        if fails_deliver_text or fails_receive_text:
            fails_total = format_number(as_float(fails_deliver_text) + as_float(fails_receive_text))
        normalized = {
            "date": row.get("date", "").strip(),
            "maturity_bucket": row.get("maturity_bucket", "").strip(),
            "dealer_category": row.get("dealer_category", "treasury").strip(),
            "net_positions_usd_millions": _optional_number(
                row.get("net_positions_usd_millions")
            ),
            "financing_usd_millions": _optional_number(row.get("financing_usd_millions")),
            "fails_to_deliver_usd_millions": fails_deliver_text,
            "fails_to_receive_usd_millions": fails_receive_text,
            "dealer_fails_total_usd_millions": fails_total,
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
    accepted = as_float(event_row.get("accepted_amount_usd_millions"))
    sibling_outstanding = as_float(context.get("sibling_outstanding_usd_millions"))
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
        "sibling_outstanding_usd_millions": context.get("sibling_outstanding_usd_millions", ""),
        "sibling_liquidity_weight": context.get("sibling_liquidity_weight", ""),
        "buyback_intensity": format_number(
            accepted / sibling_outstanding if sibling_outstanding else None
        ),
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


def _values(
    rows: list[dict[str, str]],
    field: str,
    *,
    day_min: int | None = None,
    day_max: int | None = None,
) -> list[float]:
    values: list[float] = []
    for row in rows:
        if not row.get(field):
            continue
        event_day = int(as_float(row.get("event_day")))
        if day_min is not None and event_day < day_min:
            continue
        if day_max is not None and event_day > day_max:
            continue
        values.append(as_float(row.get(field), default=float("nan")))
    return values


def _mean_for(
    rows: list[dict[str, str]],
    field: str,
    *,
    day_min: int | None = None,
    day_max: int | None = None,
) -> float | None:
    return _mean(_values(rows, field, day_min=day_min, day_max=day_max))


def _change(
    rows: list[dict[str, str]],
    field: str,
    *,
    pre_min: int | None = None,
    pre_max: int = -1,
    post_min: int = 1,
    post_max: int | None = None,
) -> float | None:
    pre = _mean_for(rows, field, day_min=pre_min, day_max=pre_max)
    post = _mean_for(rows, field, day_min=post_min, day_max=post_max)
    if pre is None or post is None:
        return None
    return post - pre


def _pretrend_change(rows: list[dict[str, str]], field: str) -> float | None:
    early = _mean_for(rows, field, day_max=-6)
    late = _mean_for(rows, field, day_min=-5, day_max=-1)
    if early is None or late is None:
        return None
    return late - early


def _nonmissing_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if row.get(field))


def _status_from_coverage(trace_rows: int, dealer_rows: int, fails_rows: int) -> str:
    if trace_rows and dealer_rows and fails_rows:
        return "trace_dealer_fails"
    if trace_rows and dealer_rows:
        return "trace_dealer_position"
    if trace_rows:
        return "trace_only"
    if dealer_rows:
        return "dealer_position_only"
    return "no_proxy_rows"


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
        pre_turnover_mean = _mean_for(rows, "trace_turnover", day_max=-1)
        post_turnover_mean = _mean_for(rows, "trace_turnover", day_min=1)
        pre_fails_mean = _mean_for(rows, "dealer_fails_total_usd_millions", day_max=-1)
        post_fails_mean = _mean_for(rows, "dealer_fails_total_usd_millions", day_min=1)
        pre_net_position_mean = _mean_for(rows, "net_positions_usd_millions", day_max=-1)
        post_net_position_mean = _mean_for(rows, "net_positions_usd_millions", day_min=1)
        pre_financing_mean = _mean_for(rows, "financing_usd_millions", day_max=-1)
        post_financing_mean = _mean_for(rows, "financing_usd_millions", day_min=1)
        first = rows[0]
        summary.append(
            {
                "operation_id": first["operation_id"],
                "event_type": first["event_type"],
                "target_maturity_bucket": first["target_maturity_bucket"],
                "comparison_maturity_bucket": first["comparison_maturity_bucket"],
                "targeted_bucket": first["targeted_bucket"],
                "accepted_amount_usd_millions": first.get("accepted_amount_usd_millions", ""),
                "buyback_intensity": first.get("buyback_intensity", ""),
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
                "pre_event_net_position_mean": format_number(pre_net_position_mean),
                "post_event_net_position_mean": format_number(post_net_position_mean),
                "post_minus_pre_net_position": format_number(
                    None
                    if pre_net_position_mean is None or post_net_position_mean is None
                    else post_net_position_mean - pre_net_position_mean
                ),
                "pre_event_financing_mean": format_number(pre_financing_mean),
                "post_event_financing_mean": format_number(post_financing_mean),
                "post_minus_pre_financing": format_number(
                    None
                    if pre_financing_mean is None or post_financing_mean is None
                    else post_financing_mean - pre_financing_mean
                ),
                "trace_rows": str(_nonmissing_count(rows, "trace_turnover")),
                "dealer_position_rows": str(_nonmissing_count(rows, "net_positions_usd_millions")),
                "dealer_fails_rows": str(
                    _nonmissing_count(rows, "dealer_fails_total_usd_millions")
                ),
                "event_window_rows": str(len(rows)),
            }
        )
    return summary


def _grouped_panel(panel_rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in panel_rows:
        grouped[(row["operation_id"], row["event_type"])].append(row)
    return grouped


def _diagnostic_rows(panel_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows_out: list[dict[str, str]] = []
    for (_operation_id, _event_type), rows in sorted(_grouped_panel(panel_rows).items()):
        targeted = [row for row in rows if row.get("targeted_bucket") == "1"]
        controls = [row for row in rows if row.get("targeted_bucket") == "0"]
        if not targeted:
            continue
        first = targeted[0]
        target_trace_change = _change(targeted, "trace_turnover")
        control_changes = [
            value
            for bucket in sorted({row["comparison_maturity_bucket"] for row in controls})
            if (
                value := _change(
                    [row for row in controls if row["comparison_maturity_bucket"] == bucket],
                    "trace_turnover",
                )
            )
            is not None
        ]
        control_trace_change = _mean(control_changes)
        pretrend_trace = _pretrend_change(targeted, "trace_turnover")
        target_net_position_change = _change(targeted, "net_positions_usd_millions")
        control_net_changes = [
            value
            for bucket in sorted({row["comparison_maturity_bucket"] for row in controls})
            if (
                value := _change(
                    [row for row in controls if row["comparison_maturity_bucket"] == bucket],
                    "net_positions_usd_millions",
                )
            )
            is not None
        ]
        control_net_change = _mean(control_net_changes)
        trace_rows = _nonmissing_count(rows, "trace_turnover")
        dealer_rows = _nonmissing_count(rows, "net_positions_usd_millions")
        fails_rows = _nonmissing_count(rows, "dealer_fails_total_usd_millions")
        pretrend_warning = (
            "1"
            if pretrend_trace is not None
            and target_trace_change is not None
            and abs(pretrend_trace) >= max(abs(target_trace_change), 1e-12) * 0.5
            else "0"
        )
        if target_trace_change is None:
            trace_status = "no_target_trace"
        elif control_trace_change is None:
            trace_status = "target_only_no_control_trace"
        elif pretrend_warning == "1":
            trace_status = "pretrend_warning"
        else:
            trace_status = "diagnostic_ready"
        rows_out.append(
            {
                "operation_id": first["operation_id"],
                "event_type": first["event_type"],
                "target_maturity_bucket": first["target_maturity_bucket"],
                "accepted_amount_usd_millions": first.get("accepted_amount_usd_millions", ""),
                "buyback_intensity": first.get("buyback_intensity", ""),
                "targeted_post_minus_pre_trace_turnover": format_number(target_trace_change),
                "control_post_minus_pre_trace_turnover_mean": format_number(control_trace_change),
                "targeted_minus_control_trace_turnover_change": format_number(
                    None
                    if target_trace_change is None or control_trace_change is None
                    else target_trace_change - control_trace_change
                ),
                "targeted_pretrend_trace_turnover_change": format_number(pretrend_trace),
                "targeted_post_minus_pre_net_position": format_number(target_net_position_change),
                "control_post_minus_pre_net_position_mean": format_number(control_net_change),
                "targeted_minus_control_net_position_change": format_number(
                    None
                    if target_net_position_change is None or control_net_change is None
                    else target_net_position_change - control_net_change
                ),
                "pretrend_warning": pretrend_warning,
                "trace_diagnostic_status": trace_status,
                "coverage_status": _status_from_coverage(trace_rows, dealer_rows, fails_rows),
            }
        )
    return rows_out


def _coverage_rows(panel_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows_out: list[dict[str, str]] = []
    for (_operation_id, _event_type), rows in sorted(_grouped_panel(panel_rows).items()):
        targeted = [row for row in rows if row.get("targeted_bucket") == "1"]
        if not targeted:
            continue
        first = targeted[0]
        trace_rows = _nonmissing_count(rows, "trace_turnover")
        dealer_position_rows = _nonmissing_count(rows, "net_positions_usd_millions")
        dealer_fails_rows = _nonmissing_count(rows, "dealer_fails_total_usd_millions")
        rows_out.append(
            {
                "operation_id": first["operation_id"],
                "event_type": first["event_type"],
                "target_maturity_bucket": first["target_maturity_bucket"],
                "event_window_rows": str(len(rows)),
                "targeted_rows": str(len(targeted)),
                "control_rows": str(len(rows) - len(targeted)),
                "trace_rows": str(trace_rows),
                "dealer_position_rows": str(dealer_position_rows),
                "dealer_fails_rows": str(dealer_fails_rows),
                "coverage_status": _status_from_coverage(
                    trace_rows,
                    dealer_position_rows,
                    dealer_fails_rows,
                ),
            }
        )
    return rows_out


def _announcement_operation_rows(summary_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    targeted = [row for row in summary_rows if row.get("targeted_bucket") == "1"]
    index = {(row["operation_id"], row["event_type"]): row for row in targeted}
    operation_ids = sorted({row["operation_id"] for row in targeted})
    rows_out: list[dict[str, str]] = []
    for operation_id in operation_ids:
        announcement = index.get((operation_id, "announcement"))
        operation = index.get((operation_id, "operation"))
        if not announcement and not operation:
            continue
        base = announcement or operation or {}
        announcement_trace = as_float(
            announcement.get("post_minus_pre_trace_turnover") if announcement else "",
            default=float("nan"),
        )
        operation_trace = as_float(
            operation.get("post_minus_pre_trace_turnover") if operation else "",
            default=float("nan"),
        )
        announcement_net = as_float(
            announcement.get("post_minus_pre_net_position") if announcement else "",
            default=float("nan"),
        )
        operation_net = as_float(
            operation.get("post_minus_pre_net_position") if operation else "",
            default=float("nan"),
        )
        rows_out.append(
            {
                "operation_id": operation_id,
                "target_maturity_bucket": base.get("target_maturity_bucket", ""),
                "accepted_amount_usd_millions": base.get("accepted_amount_usd_millions", ""),
                "buyback_intensity": base.get("buyback_intensity", ""),
                "announcement_trace_change": format_number(
                    None if announcement_trace != announcement_trace else announcement_trace
                ),
                "operation_trace_change": format_number(
                    None if operation_trace != operation_trace else operation_trace
                ),
                "operation_minus_announcement_trace_change": format_number(
                    None
                    if announcement_trace != announcement_trace
                    or operation_trace != operation_trace
                    else operation_trace - announcement_trace
                ),
                "announcement_net_position_change": format_number(
                    None if announcement_net != announcement_net else announcement_net
                ),
                "operation_net_position_change": format_number(
                    None if operation_net != operation_net else operation_net
                ),
                "operation_minus_announcement_net_position_change": format_number(
                    None
                    if announcement_net != announcement_net or operation_net != operation_net
                    else operation_net - announcement_net
                ),
            }
        )
    return rows_out


def _claim_status(
    diagnostic: Mapping[str, str],
    targeted_summary: Mapping[str, str] | None,
) -> str:
    if diagnostic.get("coverage_status") == "no_proxy_rows":
        return "coverage_limited"
    if diagnostic.get("trace_diagnostic_status") != "diagnostic_ready":
        return "coverage_limited"
    trace_change = as_float(
        diagnostic.get("targeted_minus_control_trace_turnover_change"),
        default=float("nan"),
    )
    fails_change = as_float(
        targeted_summary.get("post_minus_pre_fails") if targeted_summary else "",
        default=float("nan"),
    )
    net_position_change = as_float(
        diagnostic.get("targeted_minus_control_net_position_change"),
        default=float("nan"),
    )
    supportive = trace_change == trace_change and trace_change > 0
    adverse_fails = fails_change == fails_change and fails_change > 0
    easing_fails = fails_change == fails_change and fails_change < 0
    dealer_absorption_down = net_position_change == net_position_change and net_position_change < 0
    if supportive and (easing_fails or dealer_absorption_down):
        return "supportive_diagnostic"
    if supportive or easing_fails or dealer_absorption_down:
        return "mixed_diagnostic"
    if adverse_fails or (trace_change == trace_change and trace_change < 0):
        return "mixed_diagnostic"
    return "no_visible_signal"


def _results_triage_rows(
    diagnostic_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    targeted_summary = {
        (row["operation_id"], row["event_type"]): row
        for row in summary_rows
        if row.get("targeted_bucket") == "1"
    }
    rows_out: list[dict[str, str]] = []
    for diagnostic in diagnostic_rows:
        key = (diagnostic["operation_id"], diagnostic["event_type"])
        summary = targeted_summary.get(key)
        trace_change = as_float(
            diagnostic.get("targeted_minus_control_trace_turnover_change"),
            default=0.0,
        )
        fails_change = as_float(
            summary.get("post_minus_pre_fails") if summary else "",
            default=0.0,
        )
        net_position_change = as_float(
            diagnostic.get("targeted_minus_control_net_position_change"),
            default=0.0,
        )
        intensity = as_float(diagnostic.get("buyback_intensity"), default=0.0)
        signal_score = (
            abs(trace_change)
            + abs(fails_change) / 1_000_000
            + abs(net_position_change) / 100_000
        )
        rows_out.append(
            {
                "operation_id": diagnostic["operation_id"],
                "event_type": diagnostic["event_type"],
                "target_maturity_bucket": diagnostic["target_maturity_bucket"],
                "claim_status": _claim_status(diagnostic, summary),
                "triage_rank": "",
                "signal_score": format_number(signal_score),
                "targeted_minus_control_trace_turnover_change": diagnostic.get(
                    "targeted_minus_control_trace_turnover_change",
                    "",
                ),
                "targeted_pretrend_trace_turnover_change": diagnostic.get(
                    "targeted_pretrend_trace_turnover_change",
                    "",
                ),
                "post_minus_pre_fails": summary.get("post_minus_pre_fails", "") if summary else "",
                "post_minus_pre_net_position": (
                    summary.get("post_minus_pre_net_position", "") if summary else ""
                ),
                "targeted_minus_control_net_position_change": diagnostic.get(
                    "targeted_minus_control_net_position_change",
                    "",
                ),
                "buyback_intensity": format_number(intensity) if intensity else "",
                "accepted_amount_usd_millions": diagnostic.get(
                    "accepted_amount_usd_millions",
                    "",
                ),
                "coverage_status": diagnostic.get("coverage_status", ""),
                "trace_diagnostic_status": diagnostic.get("trace_diagnostic_status", ""),
            }
        )
    status_priority = {
        "supportive_diagnostic": 3,
        "mixed_diagnostic": 2,
        "no_visible_signal": 1,
        "coverage_limited": 0,
    }
    rows_out.sort(
        key=lambda row: (
            status_priority.get(row["claim_status"], 0),
            as_float(row["signal_score"]),
        ),
        reverse=True,
    )
    for rank, row in enumerate(rows_out, start=1):
        row["triage_rank"] = str(rank)
    return rows_out


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
    diagnostics_file = config.path("event_diagnostics")
    results_triage_file = config.path("results_triage")
    coverage_file = config.path("coverage_qa")
    announcement_operation_file = config.path("announcement_operation_summary")

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
                context.get((window_date, target_bucket))
                or context.get((month_key(window_date), target_bucket)),
            )
        )
        for control_bucket in _nearby_control_buckets(config, target_bucket):
            panel_rows.append(
                _build_panel_row(
                    event_row,
                    control_bucket,
                    False,
                    context.get((window_date, control_bucket))
                    or context.get((month_key(window_date), control_bucket)),
                )
            )

    panel_fields = _schema_fields(config, "offrun_panel") + [
        "event_date",
        "security_type",
        "offered_amount_usd_millions",
        "acceptance_ratio",
        "sibling_outstanding_usd_millions",
        "sibling_liquidity_weight",
        "trading_volume_usd_millions",
        "net_positions_usd_millions",
        "financing_usd_millions",
        "liquidity_proxy_count",
    ]
    summary_rows = _summary_rows(panel_rows)
    summary_fields = _schema_fields(config, "buyback_event_summary") + [
        "accepted_amount_usd_millions",
        "buyback_intensity",
        "pre_event_net_position_mean",
        "post_event_net_position_mean",
        "post_minus_pre_net_position",
        "pre_event_financing_mean",
        "post_event_financing_mean",
        "post_minus_pre_financing",
        "trace_rows",
        "dealer_position_rows",
        "dealer_fails_rows",
        "event_window_rows",
    ]
    diagnostic_fields = _schema_fields(config, "event_diagnostics") + [
        "accepted_amount_usd_millions",
        "buyback_intensity",
        "targeted_post_minus_pre_net_position",
        "control_post_minus_pre_net_position_mean",
        "targeted_minus_control_net_position_change",
        "coverage_status",
    ]
    triage_fields = _schema_fields(config, "results_triage") + [
        "targeted_pretrend_trace_turnover_change",
        "targeted_minus_control_net_position_change",
        "accepted_amount_usd_millions",
        "trace_diagnostic_status",
    ]
    coverage_fields = _schema_fields(config, "coverage_qa")
    announcement_operation_fields = _schema_fields(config, "announcement_operation_summary") + [
        "accepted_amount_usd_millions",
        "buyback_intensity",
        "operation_minus_announcement_net_position_change",
    ]
    write_csv(panel_output, panel_rows, panel_fields)
    write_csv(summary_file, summary_rows, summary_fields)
    diagnostic_rows = _diagnostic_rows(panel_rows)
    write_csv(diagnostics_file, diagnostic_rows, diagnostic_fields)
    write_csv(
        results_triage_file,
        _results_triage_rows(diagnostic_rows, summary_rows),
        triage_fields,
    )
    write_csv(coverage_file, _coverage_rows(panel_rows), coverage_fields)
    write_csv(
        announcement_operation_file,
        _announcement_operation_rows(summary_rows),
        announcement_operation_fields,
    )
    return panel_output, summary_file
