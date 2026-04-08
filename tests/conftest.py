"""Shared pytest configuration and helpers."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

# main.py exits at import if this is missing or too short
os.environ.setdefault("BASKET_SESSION_SECRET", "test-session-secret-" + "x" * 16)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def init_sqlite_schema(db_path: Path) -> None:
    """Apply schema.sql to an empty SQLite file."""
    schema = _repo_root() / "schema.sql"
    sql = schema.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(sql)


@pytest.fixture
def repo_root() -> Path:
    return _repo_root()
