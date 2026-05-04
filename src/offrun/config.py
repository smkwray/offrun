"""Configuration loading and validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .io import OffrunError

CONFIG_FILENAMES = ("project.yml", "source_contracts.yml", "variables.yml", "schemas.yml")


class ConfigError(OffrunError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class OffrunConfig:
    """Loaded project configuration."""

    repo_root: Path
    project: dict[str, Any]
    source_contracts: dict[str, Any]
    variables: dict[str, Any]
    schemas: dict[str, Any]

    @property
    def paths(self) -> Mapping[str, str]:
        paths = self.project.get("paths", {})
        if not isinstance(paths, Mapping):
            return {}
        return paths

    def path(self, key: str) -> Path:
        """Return a configured path resolved relative to the repository root."""

        try:
            value = self.paths[key]
        except KeyError as exc:
            raise ConfigError(f"Missing configured path key: {key}") from exc
        return self.repo_root / str(value)


def find_repo_root(start: Path | None = None) -> Path:
    """Find a repository root by walking upward from *start* or the current directory."""

    base = Path.cwd() if start is None else Path(start)
    base = base.resolve()
    candidates = [base, *base.parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "config").is_dir():
            return candidate
    return base


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from *path*."""

    if not path.exists():
        raise ConfigError(f"Required config file is missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ConfigError(f"Config file must contain a YAML mapping: {path}")
    return payload


def load_config(repo_root: Path | str | None = None) -> OffrunConfig:
    """Load all project configuration files."""

    root = find_repo_root(Path(repo_root)) if repo_root is not None else find_repo_root()
    config_dir = root / "config"
    payloads = {name: load_yaml(config_dir / name) for name in CONFIG_FILENAMES}
    return OffrunConfig(
        repo_root=root,
        project=payloads["project.yml"],
        source_contracts=payloads["source_contracts.yml"],
        variables=payloads["variables.yml"],
        schemas=payloads["schemas.yml"],
    )


def _require_mapping(payload: Mapping[str, Any], key: str, origin: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ConfigError(f"{origin} must define a mapping named {key!r}")
    return value


def _require_sequence(payload: Mapping[str, Any], key: str, origin: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{origin} must define a non-empty list named {key!r}")
    return value


def validate_config(repo_root: Path | str | None = None) -> list[str]:
    """Validate configuration files and return human-readable check messages."""

    config = load_config(repo_root)
    messages: list[str] = []

    project = _require_mapping(config.project, "project", "project.yml")
    if project.get("name") != "offrun":
        raise ConfigError("project.yml project.name must be 'offrun'")
    if "~/venvs/offrun" not in str(project.get("external_venv", "")):
        raise ConfigError("project.yml must document the external venv path ~/venvs/offrun")
    messages.append("project metadata ok")

    paths = _require_mapping(config.project, "paths", "project.yml")
    required_path_keys = {
        "buyback_operations",
        "buyback_event_calendar",
        "trace_liquidity_context",
        "dealer_liquidity_context",
        "liquidity_context_panel",
        "offrun_panel",
        "buyback_event_summary",
        "source_inventory",
        "report",
        "buyback_timeline_figure",
        "targeted_bucket_figure",
        "manifest",
    }
    missing_paths = sorted(required_path_keys.difference(paths))
    if missing_paths:
        raise ConfigError(f"project.yml paths missing keys: {', '.join(missing_paths)}")
    messages.append("path registry ok")

    claim_boundary = _require_mapping(config.project, "claim_boundary", "project.yml")
    required_phrases = _require_sequence(
        claim_boundary,
        "required_report_phrases",
        "project.yml claim_boundary",
    )
    if "descriptive market-liquidity evidence" not in required_phrases:
        raise ConfigError("claim boundary must require 'descriptive market-liquidity evidence'")
    _require_sequence(
        claim_boundary,
        "forbidden_unqualified_phrases",
        "project.yml claim_boundary",
    )
    messages.append("claim boundary ok")

    sibling_sources = _require_mapping(
        config.source_contracts,
        "sibling_sources",
        "source_contracts.yml",
    )
    for sibling in ("tdcladder", "buycurve", "liqsub"):
        sibling_payload = _require_mapping(sibling_sources, sibling, "source_contracts.yml")
        artifacts = _require_sequence(
            sibling_payload,
            "artifacts",
            f"source_contracts.yml {sibling}",
        )
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                raise ConfigError(f"Artifact contract for {sibling} must be a mapping")
            for key in ("name", "source_path", "import_path", "required_columns"):
                if key not in artifact:
                    raise ConfigError(f"Artifact contract for {sibling} missing key {key!r}")
    messages.append("sibling source contracts ok")

    public_sources = _require_mapping(
        config.source_contracts,
        "public_sources",
        "source_contracts.yml",
    )
    for source in (
        "treasury_buybacks_fiscaldata",
        "treasurydirect_buybacks",
        "finra_trace_treasury_aggregates",
        "nyfed_primary_dealer_statistics",
    ):
        _require_mapping(public_sources, source, "source_contracts.yml")
    messages.append("public source contracts ok")

    maturity_buckets = _require_mapping(config.variables, "maturity_buckets", "variables.yml")
    bucket_order = _require_sequence(maturity_buckets, "order", "variables.yml maturity_buckets")
    nearby = _require_mapping(maturity_buckets, "nearby_control_buckets", "variables.yml")
    for bucket in bucket_order:
        if bucket not in nearby:
            raise ConfigError(f"Missing nearby-control map for maturity bucket {bucket}")
    messages.append("variable registry ok")

    datasets = _require_mapping(config.schemas, "datasets", "schemas.yml")
    for dataset in (
        "buyback_operations",
        "buyback_event_calendar",
        "trace_liquidity_context",
        "dealer_liquidity_context",
        "liquidity_context_panel",
        "offrun_panel",
        "buyback_event_summary",
    ):
        dataset_payload = _require_mapping(datasets, dataset, "schemas.yml datasets")
        _require_sequence(dataset_payload, "required_columns", f"schemas.yml {dataset}")
        _require_sequence(dataset_payload, "primary_key", f"schemas.yml {dataset}")
    messages.append("schemas ok")

    return messages
