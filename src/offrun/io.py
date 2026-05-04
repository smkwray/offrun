"""Small file I/O helpers for offrun."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


class OffrunError(RuntimeError):
    """Base exception for user-facing offrun failures."""


def ensure_parent(path: Path) -> None:
    """Create the parent directory for *path* if needed."""

    path.parent.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of string dictionaries."""

    if not path.exists():
        raise OffrunError(f"CSV file does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def read_csv_header(path: Path) -> list[str]:
    """Return the header of a CSV file without reading all rows."""

    if not path.exists():
        raise OffrunError(f"CSV file does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration as exc:
            raise OffrunError(f"CSV file is empty: {path}") from exc


def count_csv_rows(path: Path) -> int:
    """Count non-header rows in a CSV file."""

    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> int:
    """Write dictionaries to CSV and return the number of rows written."""

    ensure_parent(path)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
            count += 1
    return count


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""

    if not path.exists():
        raise OffrunError(f"Text file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file."""

    ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a stable JSON document."""

    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    """Compute a SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: object, default: float = 0.0) -> float:
    """Parse a numeric value with blank-safe fallback."""

    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def format_number(value: float | int | None, digits: int = 6) -> str:
    """Format a number compactly for CSV output."""

    if value is None:
        return ""
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
