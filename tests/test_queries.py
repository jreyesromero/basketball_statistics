"""Tests for src.queries with an isolated SQLite file."""

import pytest

import src.queries as queries
from tests.conftest import init_sqlite_schema


@pytest.fixture
def stats_db(monkeypatch, tmp_path):
    db_path = tmp_path / "stats.sqlite"
    monkeypatch.setattr(queries, "DB_PATH", db_path)
    init_sqlite_schema(db_path)
    return db_path


def test_load_players_empty(stats_db) -> None:
    assert queries.load_players() == []


def test_load_players_returns_row(stats_db) -> None:
    import sqlite3

    with sqlite3.connect(stats_db) as conn:
        conn.execute(
            """
            INSERT INTO player (name, surname, address, date_of_birth)
            VALUES ('Jane', 'Doe', NULL, '1990-01-15')
            """
        )
        conn.commit()
    rows = queries.load_players()
    assert len(rows) == 1
    assert rows[0]["surname"] == "Doe"
    assert rows[0]["name"] == "Jane"
    assert rows[0]["date_of_birth"] == "1990-01-15"


def test_fetch_players_swallows_db_error(monkeypatch, tmp_path) -> None:
    bad = tmp_path / "missing-dir" / "nope.sqlite"
    monkeypatch.setattr(queries, "DB_PATH", bad)
    assert queries.fetch_players() == []


def test_load_clubs_empty(stats_db) -> None:
    assert queries.load_clubs() == []


def test_load_clubs_returns_row(stats_db) -> None:
    import sqlite3

    with sqlite3.connect(stats_db) as conn:
        conn.execute(
            """
            INSERT INTO club (name, foundation_date, address)
            VALUES ('Hoopers', '2000-06-01', 'Main St')
            """
        )
        conn.commit()
    rows = queries.load_clubs()
    assert len(rows) == 1
    assert rows[0]["name"] == "Hoopers"
    assert rows[0]["foundation_date"] == "2000-06-01"
