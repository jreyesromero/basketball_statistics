"""Tests for seasons, season teams, and team rosters."""

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
            """
            INSERT INTO player (name, surname, date_of_birth)
            VALUES (?, ?, ?)
            """,
            ("Alan", "Turing", "1999-06-01"),
        )
        conn.execute(
            "INSERT INTO club (name, foundation_date) VALUES (?, ?)",
            ("Test Club", "1990-01-01"),
        )
        conn.execute(
            "INSERT INTO club (name, foundation_date) VALUES (?, ?)",
            ("Other Club", "1991-01-01"),
        )
        conn.commit()
    return db_path


def test_season_team_and_assign_player(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    st_id = roster_repo.insert_season_team(sid, 1, user_id=1)
    teams = roster_repo.list_teams_for_season(sid)
    assert len(teams) == 1
    assert teams[0]["club_name"] == "Test Club"

    stp_id = roster_repo.insert_team_player(st_id, 1, "7", user_id=1)
    players = roster_repo.list_players_on_team(st_id)
    assert len(players) == 1
    assert players[0]["surname"] == "Lovelace"
    assert players[0]["jersey_number"] == "7"

    roster_repo.delete_team_player(stp_id, user_id=1)
    assert roster_repo.list_players_on_team(st_id) == []


def test_player_one_team_per_season(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    t1 = roster_repo.insert_season_team(sid, 1, user_id=1)
    t2 = roster_repo.insert_season_team(sid, 2, user_id=1)
    roster_repo.insert_team_player(t1, 1, None, user_id=1)
    with pytest.raises(ValueError, match="already on a team"):
        roster_repo.insert_team_player(t2, 1, None, user_id=1)


def test_delete_season_team_removes_assignments(roster_db):
    from src import roster_repo

    sid = roster_repo.insert_season("2024", "2025", user_id=1)
    st_id = roster_repo.insert_season_team(sid, 1, user_id=1)
    roster_repo.insert_team_player(st_id, 1, None, user_id=1)
    roster_repo.delete_season_team(st_id, user_id=1)
    assert roster_repo.list_teams_for_season(sid) == []
    with sqlite3.connect(roster_db) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM season_team_player WHERE season_id = ?",
            (sid,),
        ).fetchone()[0]
    assert n == 0
