"""Real-source preparation for the offrun backend."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from .config import load_config
from .io import OffrunError, as_float, format_number, read_csv, write_csv, write_json

FISCALDATA_BUYBACKS_ENDPOINT = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
    "v1/accounting/od/buybacks_operations"
)

ANALYSIS_BUCKETS = ("1-3y", "3-7y", "7-10y", "10-20y", "20-30y")


def _bucket_from_source(value: str) -> str:
    text = value.strip().lower().replace(" ", "")
    mapping = {
        "1-3y": "1-3y",
        "3-7y": "3-7y",
        "7-10y": "7-10y",
        "10-20y": "10-20y",
        "20-30y": "20-30y",
        "1moto2y": "1-3y",
        "2yto3y": "1-3y",
        "1yto7.5y": "3-7y",
        "1yto10y": "3-7y",
        "0_3m": "1-3y",
        "3_6m": "1-3y",
        "6_12m": "1-3y",
        "1_2y": "1-3y",
        "2_3y": "1-3y",
        "l2": "1-3y",
        "3yto7y": "3-7y",
        "3yto5y": "3-7y",
        "5yto7y": "3-7y",
        "3_5y": "3-7y",
        "5_7y": "3-7y",
        "g2l3": "1-3y",
        "g3l6": "3-7y",
        "g6l7": "3-7y",
        "7yto10y": "7-10y",
        "7.5yto30y": "20-30y",
        "7_10y": "7-10y",
        "g7l11": "7-10y",
        "10yto20y": "10-20y",
        "10_20y": "10-20y",
        "g11l21": "10-20y",
        "20yto30y": "20-30y",
        "10yto30y": "20-30y",
        "20_30y": "20-30y",
        "30y_plus": "20-30y",
        "g21": "20-30y",
        "g2": "3-7y",
        "g6l11": "7-10y",
        "g11": "20-30y",
        "0-1y": "1-3y",
        "0to1y": "1-3y",
        "1-5y": "3-7y",
        "1to5y": "3-7y",
        "5-10y": "7-10y",
        "5to10y": "7-10y",
        "10-20years": "10-20y",
        "20-30years": "20-30y",
        "over30y": "20-30y",
        ">30y": "20-30y",
        "greaterthan30y": "20-30y",
    }
    return mapping.get(text, "")


def _normalized_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _first_present(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    keyed = {_normalized_key(key): value for key, value in row.items()}
    for candidate in candidates:
        value = keyed.get(_normalized_key(candidate), "")
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _normalize_on_off_run(value: str) -> str:
    text = value.strip().lower().replace("_", " ").replace("-", " ")
    if not text:
        return "unknown"
    if "off" in text:
        return "off_the_run"
    if "on" in text:
        return "on_the_run"
    if "total" in text or "all" in text or "aggregate" in text:
        return "aggregate"
    return text.replace(" ", "_")


def _volume_usd_millions(row: dict[str, str]) -> float:
    raw = _first_present(
        row,
        (
            "trading_volume_usd_millions",
            "total_volume_usd_millions",
            "volume_usd_millions",
            "trading_volume",
            "total_volume",
            "volume",
            "par_volume",
            "total_par_value",
            "sum_par_value",
        ),
    )
    value = as_float(raw)
    key_text = " ".join(row.keys()).lower()
    if value and "millions" not in key_text and value > 1_000_000:
        return value / 1_000_000
    return value


def _outstanding_usd_millions(row: dict[str, str]) -> float:
    raw = _first_present(
        row,
        (
            "outstanding_usd_millions",
            "outstanding_amount_usd_millions",
            "outstanding_amount",
            "amount_outstanding",
        ),
    )
    value = as_float(raw)
    key_text = " ".join(row.keys()).lower()
    if value and "millions" not in key_text and value > 1_000_000:
        return value / 1_000_000
    return value


def _month(value: str) -> str:
    text = value.strip()
    if len(text) >= 7:
        return f"{text[:7]}-01"
    return text


def _source_path(root: Path, sibling: str, relative: str) -> Path:
    return root / sibling / relative


def _fetch_fiscaldata_rows(endpoint: str = FISCALDATA_BUYBACKS_ENDPOINT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    page_size = 500
    while True:
        query = urllib.parse.urlencode(
            {
                "page[number]": str(page),
                "page[size]": str(page_size),
                "sort": "operation_date",
            }
        )
        url = f"{endpoint}?{query}"
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise OffrunError(f"FiscalData response has no data list: {url}")
        rows.extend(row for row in data if isinstance(row, dict))
        if len(data) < page_size:
            break
        page += 1
    return rows


def download_fiscaldata_buybacks(
    repo_root: Path | str | None = None,
    *,
    output_path: Path | str | None = None,
) -> Path:
    """Download FiscalData Treasury buyback operations into project-local raw data."""

    config = load_config(repo_root)
    output = (
        Path(output_path)
        if output_path is not None
        else config.repo_root / "data/raw/fiscaldata/treasury_securities_buybacks.csv"
    )
    rows = _fetch_fiscaldata_rows()
    fields = [
        "operation_date",
        "operation_start_time_est",
        "operation_close_time_est",
        "settlement_date",
        "preliminary_ann_pdf",
        "preliminary_ann_xml",
        "final_ann_pdf",
        "final_ann_xml",
        "results_pdf",
        "results_xml",
        "special_ann_pdf",
        "operation_type",
        "security_type",
        "maturity_bucket",
        "nbr_issues_accepted",
        "total_par_amt_offered",
        "par_amt_per_offer",
        "max_par_amt_redeemed",
        "max_nbr_offers",
        "nbr_issues_eligible",
        "total_par_amt_accepted",
    ]
    write_csv(output, rows, fields)
    write_json(
        output.with_suffix(".manifest.json"),
        {
            "source": "FiscalData Treasury Securities Buybacks",
            "endpoint": FISCALDATA_BUYBACKS_ENDPOINT,
            "row_count": len(rows),
        },
    )
    return output


def _buyback_input(config_root: Path, sibling_root: Path, explicit: Path | str | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    local = config_root / "data/raw/fiscaldata/treasury_securities_buybacks.csv"
    if local.exists():
        return local
    sibling = _source_path(sibling_root, "qrawatch", "data/raw/fiscaldata/buybacks_operations.csv")
    if sibling.exists():
        return sibling
    raise OffrunError(
        "No buyback source found. Run download-fiscaldata-buybacks or provide --buybacks-input."
    )


def normalize_buyback_operations(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
    input_path: Path | str | None = None,
    output_path: Path | str | None = None,
) -> Path:
    """Normalize raw FiscalData/qrawatch buyback operations into offrun's input schema."""

    config = load_config(repo_root)
    root = Path(sibling_root).resolve()
    source = _buyback_input(config.repo_root, root, input_path)
    output = (
        Path(output_path)
        if output_path is not None
        else config.repo_root / "data/imported/buybacks/buyback_operations.csv"
    )
    rows: list[dict[str, str]] = []
    for index, row in enumerate(read_csv(source), start=1):
        operation_date = row.get("operation_date", "").strip()
        bucket = _bucket_from_source(row.get("maturity_bucket", ""))
        if not operation_date or not bucket:
            continue
        security_type = row.get("security_type", "").strip()
        offered = as_float(
            row.get("total_par_amt_offered")
            or as_float(row.get("offered_amount_usd_millions")) * 1_000_000
        )
        accepted = as_float(
            row.get("total_par_amt_accepted")
            or as_float(row.get("accepted_amount_usd_millions")) * 1_000_000
        )
        if accepted <= 0:
            continue
        operation_key = operation_date.replace("-", "")
        rows.append(
            {
                "operation_id": f"bb_{operation_key}_{index:04d}",
                "announcement_date": operation_date,
                "operation_date": operation_date,
                "security_type": security_type,
                "maturity_bucket": bucket,
                "offered_amount_usd_millions": format_number(offered / 1_000_000),
                "accepted_amount_usd_millions": format_number(accepted / 1_000_000),
                "operation_purpose": row.get("operation_type", "").strip(),
                "source_family": "fiscaldata_treasury_buybacks",
            }
        )
    fields = [
        "operation_id",
        "announcement_date",
        "operation_date",
        "security_type",
        "maturity_bucket",
        "offered_amount_usd_millions",
        "accepted_amount_usd_millions",
        "operation_purpose",
        "source_family",
    ]
    write_csv(output, rows, fields)
    return output


def normalize_tdcladder_context(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
) -> Path:
    """Normalize tdcladder bucket-level stock context for offrun joins."""

    config = load_config(repo_root)
    source = _source_path(
        Path(sibling_root).resolve(),
        "tdcladder",
        "data/clean/liquidity_weighted_treasury_supply_by_bucket.csv",
    )
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in read_csv(source):
        if row.get("weight_family") != "fixed_baseline":
            continue
        if row.get("supply_basis") != "outstanding_stock":
            continue
        bucket = _bucket_from_source(row.get("maturity_bucket", ""))
        if not bucket:
            continue
        key = (_month(row.get("month", "")), bucket)
        supply = as_float(row.get("treasury_supply_raw")) / 1_000_000
        liquid = as_float(row.get("liquid_treasury_supply")) / 1_000_000
        grouped[key]["supply"] += supply
        grouped[key]["liquid"] += liquid
    rows = []
    for (date, bucket), values in sorted(grouped.items()):
        supply = values["supply"]
        rows.append(
            {
                "date": date,
                "maturity_bucket": bucket,
                "outstanding_usd_millions": format_number(supply),
                "liquid_supply_usd_millions": format_number(values["liquid"]),
                "liquidity_weight": format_number(values["liquid"] / supply if supply else None),
            }
        )
    output = config.repo_root / "data/imported/tdcladder/monthly_ladder_panel.csv"
    write_csv(
        output,
        rows,
        [
            "date",
            "maturity_bucket",
            "outstanding_usd_millions",
            "liquid_supply_usd_millions",
            "liquidity_weight",
        ],
    )
    return output


def _direct_trace_input(config_root: Path) -> Path | None:
    candidates = [
        config_root / "data/raw/finra/trace_treasury_aggregates.csv",
        config_root / "data/raw/trace/trace_treasury_aggregates.csv",
        config_root / "data/imported/trace/finra_trace_treasury_aggregates.csv",
    ]
    return next((path for path in candidates if path.exists()), None)


def normalize_direct_finra_trace_context(
    repo_root: Path | str | None = None,
    *,
    input_path: Path | str | None = None,
    output_path: Path | str | None = None,
) -> Path:
    """Normalize a FINRA Treasury aggregate CSV export into offrun TRACE input."""

    config = load_config(repo_root)
    source = Path(input_path) if input_path is not None else _direct_trace_input(config.repo_root)
    if source is None:
        raise OffrunError(
            "No direct FINRA TRACE aggregate CSV found under data/raw/finra, data/raw/trace, "
            "or data/imported/trace."
        )
    rows = []
    for row in read_csv(source):
        date = _first_present(
            row,
            (
                "date",
                "as_of_date",
                "trade_date",
                "report_date",
                "reporting_date",
                "calendar_date",
            ),
        )
        bucket = _bucket_from_source(
            _first_present(
                row,
                (
                    "maturity_bucket",
                    "remaining_maturity_bucket",
                    "remaining_maturity",
                    "maturity",
                    "tenor",
                ),
            )
        )
        if not date or not bucket:
            continue
        security_type = _first_present(
            row,
            (
                "trace_security_type",
                "security_type",
                "product",
                "security",
                "asset_type",
                "instrument_type",
            ),
        )
        on_off_run = _normalize_on_off_run(
            _first_present(
                row,
                ("on_off_run", "on/off_run", "on_off_the_run", "run_status", "security_status"),
            )
        )
        volume = _volume_usd_millions(row)
        outstanding = _outstanding_usd_millions(row)
        rows.append(
            {
                "date": date[:10],
                "maturity_bucket": bucket,
                "trace_category": "FINRA Treasury aggregate",
                "on_off_run": on_off_run,
                "trace_security_type": security_type,
                "trading_volume_usd_millions": format_number(volume),
                "outstanding_usd_millions": format_number(outstanding if outstanding else None),
                "trace_turnover": format_number(volume / outstanding if outstanding else None),
                "trace_source_granularity": "finra_aggregate_maturity_on_off_run",
                "source_family": "finra_treasury_aggregate_direct_csv",
            }
        )
    if not rows:
        raise OffrunError(f"No usable FINRA TRACE aggregate rows found in {source}")
    output = (
        Path(output_path)
        if output_path is not None
        else config.repo_root / "data/imported/trace/trace_treasury_aggregates.csv"
    )
    write_csv(
        output,
        rows,
        [
            "date",
            "maturity_bucket",
            "trace_category",
            "on_off_run",
            "trace_security_type",
            "trading_volume_usd_millions",
            "outstanding_usd_millions",
            "trace_turnover",
            "trace_source_granularity",
            "source_family",
        ],
    )
    return output


def normalize_buycurve_context(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
) -> Path:
    """Normalize buycurve monthly issuance and maturity context."""

    config = load_config(repo_root)
    source = _source_path(
        Path(sibling_root).resolve(),
        "buycurve",
        "data/clean/monthly_issuance_maturity_panel.csv",
    )
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in read_csv(source):
        bucket = _bucket_from_source(row.get("maturity_bucket", ""))
        if not bucket:
            continue
        key = (_month(row.get("month", "")), bucket)
        accepted = as_float(row.get("accepted_amount_sum")) / 1_000_000
        grouped[key]["accepted"] += accepted
        grouped[key]["weighted_maturity"] += accepted * as_float(row.get("weighted_maturity_years"))
        grouped[key]["bill_amount"] += accepted if row.get("security_type") == "Bill" else 0.0
    rows = []
    for (date, bucket), values in sorted(grouped.items()):
        accepted = values["accepted"]
        rows.append(
            {
                "date": date,
                "maturity_bucket": bucket,
                "gross_issuance_usd_millions": format_number(accepted),
                "bill_share": format_number(values["bill_amount"] / accepted if accepted else 0.0),
                "wam_months": format_number(
                    12 * values["weighted_maturity"] / accepted if accepted else None
                ),
            }
        )
    output = config.repo_root / "data/imported/buycurve/monthly_issuance_maturity_context.csv"
    write_csv(
        output,
        rows,
        ["date", "maturity_bucket", "gross_issuance_usd_millions", "bill_share", "wam_months"],
    )
    return output


def normalize_liqsub_context(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
) -> Path:
    """Normalize liqsub monthly plumbing context."""

    config = load_config(repo_root)
    source = _source_path(
        Path(sibling_root).resolve(),
        "liqsub",
        "data/clean/monthly_liquidity_substitution_panel.csv",
    )
    rows = []
    for row in read_csv(source):
        rows.append(
            {
                "date": _month(row.get("month", "")),
                "tga_usd_millions": row.get("tga", ""),
                "reserves_usd_millions": row.get("reserves", ""),
                "mmf_assets_usd_millions": row.get("total_mmf_assets", ""),
                "on_rrp_usd_millions": row.get("on_rrp", ""),
            }
        )
    output = config.repo_root / "data/imported/liqsub/monthly_liquidity_plumbing.csv"
    write_csv(
        output,
        rows,
        [
            "date",
            "tga_usd_millions",
            "reserves_usd_millions",
            "mmf_assets_usd_millions",
            "on_rrp_usd_millions",
        ],
    )
    return output


def normalize_trace_context(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
) -> Path:
    """Normalize public aggregate TRACE turnover context from tdcladder."""

    config = load_config(repo_root)
    direct_trace = _direct_trace_input(config.repo_root)
    if direct_trace is not None:
        return normalize_direct_finra_trace_context(config.repo_root, input_path=direct_trace)
    source = _source_path(
        Path(sibling_root).resolve(),
        "tdcladder",
        "data/raw/market_liquidity/turnover_by_maturity.csv",
    )
    rows = []
    for row in read_csv(source):
        security_type = row.get("security_type", "")
        if security_type not in {"Coupon", "TIPS"}:
            continue
        for bucket in ANALYSIS_BUCKETS:
            rows.append(
                {
                    "date": _month(row.get("month", "")),
                    "maturity_bucket": bucket,
                    "trace_category": f"{security_type} public aggregate",
                    "on_off_run": "aggregate",
                    "trace_security_type": security_type,
                    "trading_volume_usd_millions": format_number(
                        as_float(row.get("trace_volume")) / 1_000_000
                    ),
                    "outstanding_usd_millions": format_number(
                        as_float(row.get("outstanding_amount")) / 1_000_000
                    ),
                    "trace_turnover": "",
                    "trace_source_granularity": "tdcladder_reused_public_aggregate",
                    "source_family": "tdcladder_finra_trace_public_aggregate",
                }
            )
    output = config.repo_root / "data/imported/trace/trace_treasury_aggregates.csv"
    write_csv(
        output,
        rows,
        [
            "date",
            "maturity_bucket",
            "trace_category",
            "on_off_run",
            "trace_security_type",
            "trading_volume_usd_millions",
            "outstanding_usd_millions",
            "trace_turnover",
            "trace_source_granularity",
            "source_family",
        ],
    )
    return output


def normalize_dealer_context(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
) -> Path:
    """Normalize primary-dealer positions from buycurve's cleaned NY Fed context."""

    config = load_config(repo_root)
    source = _source_path(
        Path(sibling_root).resolve(),
        "buycurve",
        "data/interim/primary_dealer_context_clean.csv",
    )
    timeseries_source = _source_path(
        Path(sibling_root).resolve(),
        "buycurve",
        "data/raw/validation/primary_dealer/pd_timeseries.csv",
    )
    grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in read_csv(source):
        if row.get("measure") != "net_position":
            continue
        bucket = _bucket_from_source(row.get("remaining_maturity_bucket", ""))
        if not bucket:
            continue
        key = (row.get("as_of_date", ""), bucket)
        grouped[key]["net_position"] += as_float(row.get("value")) / 1_000_000
    series_fields = {
        "PDFTD-USTET": "fails_deliver",
        "PDFTD-UST": "fails_deliver",
        "PDFTR-USTET": "fails_receive",
        "PDFTR-UST": "fails_receive",
        "PDSIOSB-UTSETTOT": "financing",
        "PDSIOSB-UTSTTOT": "financing",
        "PDSOOS-UTSETTOT": "financing",
        "PDSOOS-UTSTTOT": "financing",
    }
    if timeseries_source.exists():
        for row in read_csv(timeseries_source):
            field = series_fields.get(row.get("Time Series", ""))
            if field is None:
                continue
            value = as_float(row.get("Value (millions)"), default=float("nan"))
            if value != value:
                continue
            for bucket in ANALYSIS_BUCKETS:
                grouped[(row.get("As Of Date", ""), bucket)][field] += value
    rows = []
    for (date, bucket), values in sorted(grouped.items()):
        rows.append(
            {
                "date": date,
                "maturity_bucket": bucket,
                "dealer_category": "primary_dealer_position_financing_fails",
                "net_positions_usd_millions": format_number(
                    values["net_position"] if values.get("net_position") else None
                ),
                "financing_usd_millions": format_number(
                    values["financing"] if values.get("financing") else None
                ),
                "fails_to_deliver_usd_millions": format_number(
                    values["fails_deliver"] if values.get("fails_deliver") else None
                ),
                "fails_to_receive_usd_millions": format_number(
                    values["fails_receive"] if values.get("fails_receive") else None
                ),
                "source_family": "buycurve_nyfed_primary_dealer_aggregate_diagnostics",
            }
        )
    output = config.repo_root / "data/imported/dealer/primary_dealer_statistics.csv"
    write_csv(
        output,
        rows,
        [
            "date",
            "maturity_bucket",
            "dealer_category",
            "net_positions_usd_millions",
            "financing_usd_millions",
            "fails_to_deliver_usd_millions",
            "fails_to_receive_usd_millions",
            "source_family",
        ],
    )
    return output


def prepare_real_inputs(
    repo_root: Path | str | None = None,
    *,
    sibling_root: Path | str = "..",
    buybacks_input: Path | str | None = None,
    download_buybacks: bool = False,
) -> list[Path]:
    """Prepare all ignored normalized inputs needed by ``make real-package``."""

    config = load_config(repo_root)
    if download_buybacks:
        try:
            download_fiscaldata_buybacks(config.repo_root)
        except Exception as exc:
            fallback = _source_path(
                Path(sibling_root).resolve(),
                "qrawatch",
                "data/raw/fiscaldata/buybacks_operations.csv",
            )
            if not fallback.exists():
                raise OffrunError(f"FiscalData buyback download failed: {exc}") from exc
    outputs = [
        normalize_buyback_operations(
            config.repo_root,
            sibling_root=sibling_root,
            input_path=buybacks_input,
        ),
        normalize_tdcladder_context(config.repo_root, sibling_root=sibling_root),
        normalize_buycurve_context(config.repo_root, sibling_root=sibling_root),
        normalize_liqsub_context(config.repo_root, sibling_root=sibling_root),
        normalize_trace_context(config.repo_root, sibling_root=sibling_root),
        normalize_dealer_context(config.repo_root, sibling_root=sibling_root),
    ]
    return outputs
