"""Source contract validation and sibling artifact copying."""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import OffrunConfig, load_config
from .io import OffrunError, count_csv_rows, ensure_parent, read_csv_header, write_csv


class ContractError(OffrunError):
    """Raised when source contracts are not satisfied."""


@dataclass(frozen=True)
class SourceArtifact:
    """One configured sibling artifact contract."""

    sibling: str
    name: str
    source_path: Path
    import_path: Path
    required_columns: tuple[str, ...]
    required: bool
    role: str


@dataclass(frozen=True)
class SourceStatus:
    """Validation status for one source artifact."""

    sibling: str
    artifact: str
    source_path: Path
    import_path: Path
    required: bool
    exists: bool
    row_count: int
    missing_columns: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True when the artifact exists and has all required columns."""

        return self.exists and not self.missing_columns

    def as_row(self) -> dict[str, str]:
        """Return a CSV-serializable inventory row."""

        return {
            "source_family": self.sibling,
            "artifact": self.artifact,
            "source_path": str(self.source_path),
            "import_path": str(self.import_path),
            "required": str(self.required).lower(),
            "exists": str(self.exists).lower(),
            "row_count": str(self.row_count),
            "missing_columns": ";".join(self.missing_columns),
            "status": "ok" if self.ok else "missing_or_incomplete",
        }


def _artifact_required(
    sibling_payload: Mapping[str, Any],
    artifact_payload: Mapping[str, Any],
) -> bool:
    sibling_required = bool(sibling_payload.get("required", False))
    artifact_required = bool(artifact_payload.get("required", sibling_required))
    return sibling_required and artifact_required


def iter_sibling_artifacts(
    config: OffrunConfig | None = None,
    repo_root: Path | str | None = None,
) -> list[SourceArtifact]:
    """Return configured sibling artifact contracts."""

    loaded = load_config(repo_root) if config is None else config
    sibling_sources = loaded.source_contracts.get("sibling_sources", {})
    if not isinstance(sibling_sources, Mapping):
        raise ContractError("source_contracts.yml sibling_sources must be a mapping")

    artifacts: list[SourceArtifact] = []
    for sibling, sibling_payload in sibling_sources.items():
        if not isinstance(sibling_payload, Mapping):
            continue
        role = str(sibling_payload.get("role", ""))
        for artifact_payload in sibling_payload.get("artifacts", []):
            if not isinstance(artifact_payload, Mapping):
                continue
            required_columns = tuple(
                str(col) for col in artifact_payload.get("required_columns", [])
            )
            artifacts.append(
                SourceArtifact(
                    sibling=str(sibling),
                    name=str(artifact_payload["name"]),
                    source_path=Path(str(artifact_payload["source_path"])),
                    import_path=loaded.repo_root / str(artifact_payload["import_path"]),
                    required_columns=required_columns,
                    required=_artifact_required(sibling_payload, artifact_payload),
                    role=role,
                )
            )
    return artifacts


def validate_sibling_sources(
    sibling_root: Path | str,
    repo_root: Path | str | None = None,
    *,
    strict: bool = False,
    write_inventory: bool = True,
) -> list[SourceStatus]:
    """Validate configured sibling artifacts under *sibling_root*."""

    config = load_config(repo_root)
    root = Path(sibling_root).resolve()
    statuses: list[SourceStatus] = []
    for artifact in iter_sibling_artifacts(config):
        source_path = root / artifact.sibling / artifact.source_path
        exists = source_path.exists()
        missing_columns: tuple[str, ...] = ()
        row_count = 0
        if exists:
            header = read_csv_header(source_path)
            missing_columns = tuple(col for col in artifact.required_columns if col not in header)
            row_count = count_csv_rows(source_path)
        statuses.append(
            SourceStatus(
                sibling=artifact.sibling,
                artifact=artifact.name,
                source_path=source_path,
                import_path=artifact.import_path,
                required=artifact.required,
                exists=exists,
                row_count=row_count,
                missing_columns=missing_columns,
            )
        )

    if write_inventory:
        write_source_inventory(config.path("source_inventory"), statuses)

    failed = [status for status in statuses if status.required and not status.ok]
    if strict and failed:
        detail = ", ".join(f"{status.sibling}:{status.artifact}" for status in failed)
        raise ContractError(f"Required sibling source contracts failed: {detail}")
    return statuses


def write_source_inventory(path: Path, statuses: list[SourceStatus]) -> int:
    """Write a source inventory CSV from validation statuses."""

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
    return write_csv(path, [status.as_row() for status in statuses], fieldnames)


def copy_sibling_outputs(
    sibling_root: Path | str,
    repo_root: Path | str | None = None,
    *,
    overwrite: bool = False,
    strict: bool = False,
) -> list[Path]:
    """Copy configured sibling artifacts into ignored ``data/imported`` paths."""

    config = load_config(repo_root)
    statuses = validate_sibling_sources(
        sibling_root,
        repo_root=config.repo_root,
        strict=strict,
        write_inventory=True,
    )
    copied: list[Path] = []
    for status in statuses:
        if not status.ok:
            continue
        destination = status.import_path
        if destination.exists() and not overwrite:
            continue
        ensure_parent(destination)
        shutil.copy2(status.source_path, destination)
        copied.append(destination)
    return copied
