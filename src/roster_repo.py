"""Seasons, season teams (clubs in a season), team rosters, and audit log (SQLite)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.db_paths import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _audit(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    action: str,
    user_id: int | None,
    details: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (entity_type, entity_id, action, changed_by_user_id, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (entity_type, entity_id, action, user_id, json.dumps(details, default=str)),
    )


def list_seasons() -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT s.season_id, s.start_year, s.end_year,
                   (SELECT COUNT(*) FROM season_team st WHERE st.season_id = s.season_id)
                   AS team_count
            FROM season s
            ORDER BY s.start_year DESC, s.end_year DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_season(season_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT season_id, start_year, end_year FROM season WHERE season_id = ?",
            (season_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def insert_season(start_year: str, end_year: str, user_id: int) -> int:
    sy, ey = start_year.strip(), end_year.strip()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO season (start_year, end_year) VALUES (?, ?)",
            (sy, ey),
        )
        sid = int(cur.lastrowid)
        _audit(conn, "season", sid, "INSERT", user_id, {"start_year": sy, "end_year": ey})
        conn.commit()
        return sid


def list_teams_for_season(season_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT st.season_team_id, st.season_id, st.club_id, c.name AS club_name,
                   (SELECT COUNT(*) FROM season_team_player stp
                    WHERE stp.season_team_id = st.season_team_id) AS player_count
            FROM season_team st
            JOIN club c ON c.club_id = st.club_id
            WHERE st.season_id = ?
            ORDER BY c.name COLLATE NOCASE
            """,
            (season_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_season_teams_for_club(club_id: int) -> list[dict[str, Any]]:
    """Seasons in which this club is registered as a team (for roster links)."""
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT st.season_team_id, st.season_id, s.start_year, s.end_year
            FROM season_team st
            JOIN season s ON s.season_id = st.season_id
            WHERE st.club_id = ?
            ORDER BY s.start_year DESC, s.end_year DESC
            """,
            (club_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_clubs_not_in_season(season_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT c.club_id, c.name
            FROM club c
            WHERE c.club_id NOT IN (
                SELECT club_id FROM season_team WHERE season_id = ?
            )
            ORDER BY c.name COLLATE NOCASE
            """,
            (season_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def insert_season_team(season_id: int, club_id: int, user_id: int) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO season_team (season_id, club_id)
            VALUES (?, ?)
            """,
            (season_id, club_id),
        )
        st_id = int(cur.lastrowid)
        _audit(
            conn,
            "season_team",
            st_id,
            "INSERT",
            user_id,
            {"season_id": season_id, "club_id": club_id},
        )
        conn.commit()
        return st_id


def delete_season_team(season_team_id: int, user_id: int) -> None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT season_id, club_id FROM season_team WHERE season_team_id = ?",
            (season_team_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Team not found.")
        conn.execute(
            "DELETE FROM season_team WHERE season_team_id = ?",
            (season_team_id,),
        )
        _audit(
            conn,
            "season_team",
            season_team_id,
            "DELETE",
            user_id,
            {"season_id": row["season_id"], "club_id": row["club_id"]},
        )
        conn.commit()


def fetch_season_team(season_team_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT st.season_team_id, st.season_id, st.club_id, c.name AS club_name,
                   s.start_year, s.end_year
            FROM season_team st
            JOIN club c ON c.club_id = st.club_id
            JOIN season s ON s.season_id = st.season_id
            WHERE st.season_team_id = ?
            """,
            (season_team_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_players_on_team(season_team_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT stp.season_team_player_id, stp.player_id, stp.jersey_number,
                   p.surname, p.name
            FROM season_team_player stp
            JOIN player p ON p.player_id = stp.player_id
            WHERE stp.season_team_id = ?
            ORDER BY p.surname COLLATE NOCASE, p.name COLLATE NOCASE
            """,
            (season_team_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_players_not_assigned_in_season(season_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT p.player_id, p.surname, p.name
            FROM player p
            WHERE p.player_id NOT IN (
                SELECT player_id FROM season_team_player WHERE season_id = ?
            )
            ORDER BY p.surname COLLATE NOCASE, p.name COLLATE NOCASE
            """,
            (season_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def insert_team_player(
    season_team_id: int,
    player_id: int,
    jersey_number: str | None,
    user_id: int,
) -> int:
    jersey = (jersey_number or "").strip() or None
    with _connect() as conn:
        cur = conn.execute(
            "SELECT season_id FROM season_team WHERE season_team_id = ?",
            (season_team_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Team not found.")
        season_id = int(row["season_id"])
        cur = conn.execute(
            """
            SELECT 1 FROM season_team_player
            WHERE player_id = ? AND season_id = ?
            """,
            (player_id, season_id),
        )
        if cur.fetchone():
            raise ValueError("This player is already on a team in this season.")

        cur = conn.execute(
            """
            INSERT INTO season_team_player (season_team_id, season_id, player_id, jersey_number)
            VALUES (?, ?, ?, ?)
            """,
            (season_team_id, season_id, player_id, jersey),
        )
        stp_id = int(cur.lastrowid)
        _audit(
            conn,
            "season_team_player",
            stp_id,
            "INSERT",
            user_id,
            {
                "season_team_id": season_team_id,
                "season_id": season_id,
                "player_id": player_id,
                "jersey_number": jersey,
            },
        )
        conn.commit()
        return stp_id


def fetch_season_id_for_team_player_row(season_team_player_id: int) -> int | None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT season_id FROM season_team_player WHERE season_team_player_id = ?",
            (season_team_player_id,),
        )
        row = cur.fetchone()
        return int(row["season_id"]) if row else None


def fetch_season_team_id_for_team_player_row(season_team_player_id: int) -> int | None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT season_team_id FROM season_team_player WHERE season_team_player_id = ?",
            (season_team_player_id,),
        )
        row = cur.fetchone()
        return int(row["season_team_id"]) if row else None


def delete_team_player(season_team_player_id: int, user_id: int) -> None:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT season_team_id, season_id, player_id
            FROM season_team_player
            WHERE season_team_player_id = ?
            """,
            (season_team_player_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Assignment not found.")
        conn.execute(
            "DELETE FROM season_team_player WHERE season_team_player_id = ?",
            (season_team_player_id,),
        )
        _audit(
            conn,
            "season_team_player",
            season_team_player_id,
            "DELETE",
            user_id,
            {
                "season_team_id": row["season_team_id"],
                "season_id": row["season_id"],
                "player_id": row["player_id"],
            },
        )
        conn.commit()


def list_audit_log(*, limit: int = 200) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 500))
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT a.audit_id, a.entity_type, a.entity_id, a.action, a.changed_at,
                   a.changed_by_user_id, a.details, u.email AS changed_by_email
            FROM audit_log a
            LEFT JOIN users u ON u.user_id = a.changed_by_user_id
            ORDER BY a.audit_id DESC
            LIMIT ?
            """,
            (lim,),
        )
        rows = []
        for row in cur.fetchall():
            d = dict(row)
            if d.get("details"):
                try:
                    d["details_parsed"] = json.loads(d["details"])
                except json.JSONDecodeError:
                    d["details_parsed"] = None
            rows.append(d)
        return rows
