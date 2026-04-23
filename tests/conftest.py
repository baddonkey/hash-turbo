"""Shared test fixtures for hash-turbo."""

from pathlib import Path
from typing import Callable

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--visual",
        action="store_true",
        default=False,
        help="Show GUI widgets during tests so you can watch them run.",
    )
    parser.addoption(
        "--stress",
        action="store_true",
        default=False,
        help="Run stress tests (1 000 × 1 MB files, ~1 GB disk).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item],
) -> None:
    if config.getoption("--stress"):
        return
    skip = pytest.mark.skip(reason="needs --stress to run")
    for item in items:
        if "stress" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file with known content."""
    path = tmp_path / "sample.txt"
    path.write_text("hello")
    return path


@pytest.fixture
def sample_file_factory(tmp_path: Path) -> Callable[[str, str], Path]:
    """Factory fixture to create files with custom name and content."""

    def _create(name: str, content: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    return _create


@pytest.fixture
def sample_binary_file(tmp_path: Path) -> Path:
    """Create a binary file with known content."""
    path = tmp_path / "sample.bin"
    path.write_bytes(b"\x00\x01\x02\x03")
    return path
