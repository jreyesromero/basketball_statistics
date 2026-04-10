"""Tests for seasons, enrollments, roster stints, and audit log."""

from __future__ import annotations

import sqlite3

import pytest

from tests.conftest import init_sqlite_schema


@pytest.fixture
def roster_db(tmp_path, monkeypatch):
    db_path = tmp_path / "roster_test.sqlite"
    init_sqlite_schema(db_path)
    monkeypatch.setattr("src.roster_repo.DB_PATH", db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            ("roster-test@example.com", "dummy-hash"),
        )
        conn.execute(
            """
            INSERT INTO player (name, surname, date_of_birth)
            VALUES (?, ?, ?)
            """,
            ("Ada", "Lovelace", "2000-01-01"),
        )
        conn.execute(
            "INSERT INTO club (name, foundation_date) VALUES (?, ?)",
            ("Test Club", "1990-01-01"),
        )
        conn.commit()
    return db_path


def test_insert_season_and_enrollment(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    assert sid >= 1
    ps_id = roster_repo.insert_player_season(1, sid, user_id=1)
    ps = roster_repo.fetch_player_season(ps_id)
    assert ps["surname"] == "Lovelace"
    assert ps["start_year"] == "2024"


def test_new_stint_auto_closes_previous(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    ps_id = roster_repo.insert_player_season(1, sid, user_id=1)
    r1 = roster_repo.insert_roster_stint(
        ps_id, 1, "2024-01-01", "10", user_id=1
    )
    r2 = roster_repo.insert_roster_stint(
        ps_id, 1, "2024-06-01", None, user_id=1
    )
    assert r2 > r1
    stints = roster_repo.list_roster_stints(ps_id)
    assert len(stints) == 2
    first = next(s for s in stints if s["roster_stint_id"] == r1)
    second = next(s for s in stints if s["roster_stint_id"] == r2)
    assert first["end_date"] == "2024-05-31"
    assert second["end_date"] is None


def test_new_stint_rejects_invalid_close(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    ps_id = roster_repo.insert_player_season(1, sid, user_id=1)
    roster_repo.insert_roster_stint(ps_id, 1, "2024-06-01", None, user_id=1)
    with pytest.raises(ValueError, match="before it started"):
        roster_repo.insert_roster_stint(ps_id, 1, "2024-01-01", None, user_id=1)


def test_multiple_open_stints_raises(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    ps_id = roster_repo.insert_player_season(1, sid, user_id=1)
    with sqlite3.connect(roster_db) as conn:
        conn.execute(
            """
            INSERT INTO roster_stint (player_season_id, club_id, start_date, end_date, enabled, jersey_number)
            VALUES (?, 1, '2024-01-01', NULL, 1, NULL)
            """,
            (ps_id,),
        )
        conn.execute(
            """
            INSERT INTO roster_stint (player_season_id, club_id, start_date, end_date, enabled, jersey_number)
            VALUES (?, 1, '2024-02-01', NULL, 1, NULL)
            """,
            (ps_id,),
        )
        conn.commit()
    with pytest.raises(ValueError, match="More than one open stint"):
        roster_repo.insert_roster_stint(ps_id, 1, "2024-09-01", None, user_id=1)
