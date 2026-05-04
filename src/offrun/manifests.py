"""Output manifest writer."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .io import count_csv_rows, file_sha256, write_json


def _manifest_entry(repo_root: Path, path: Path) -> dict[str, Any]:
    relative = path.relative_to(repo_root).as_posix()
    entry: dict[str, Any] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }
    if path.suffix.lower() == ".csv":
        entry["rows"] = count_csv_rows(path)
    return entry


def _candidate_paths(repo_root: Path) -> list[Path]:
    patterns = [
        "config/*.yml",
        "data/derived/*.csv",
        "output/tables/*.csv",
        "output/reports/*.md",
        "output/figures/*.svg",
    ]
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(sorted(repo_root.glob(pattern)))
    return [path for path in paths if path.is_file()]


def write_output_manifest(
    repo_root: Path | str | None = None,
    *,
    output_path: Path | str | None = None,
) -> Path:
    """Write a JSON manifest of configuration and generated outputs."""

    config = load_config(repo_root)
    manifest_path = Path(output_path) if output_path is not None else config.path("manifest")
    entries = [
        _manifest_entry(config.repo_root, path) for path in _candidate_paths(config.repo_root)
    ]
    payload: dict[str, Any] = {
        "project": "offrun",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "claim_boundary": "descriptive market-liquidity evidence only",
        "entries": entries,
    }
    write_json(manifest_path, payload)
    return manifest_path
