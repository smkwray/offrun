from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture()
def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture()
def temp_repo(tmp_path: Path, package_root: Path) -> Path:
    for name in ("config",):
        shutil.copytree(package_root / name, tmp_path / name)
    shutil.copytree(package_root / "tests" / "fixtures", tmp_path / "tests" / "fixtures")
    return tmp_path
