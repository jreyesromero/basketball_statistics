"""Seasons, player enrollments, roster stints, and audit log (SQLite)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
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
                   (SELECT COUNT(*) FROM player_season ps WHERE ps.season_id = s.season_id)
                   AS enrollment_count
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


def list_enrollments_for_season(season_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT ps.player_season_id, ps.player_id, ps.season_id,
                   p.surname, p.name, p.player_id
            FROM player_season ps
            JOIN player p ON p.player_id = ps.player_id
            WHERE ps.season_id = ?
            ORDER BY p.surname COLLATE NOCASE, p.name COLLATE NOCASE
            """,
            (season_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def list_players_not_in_season(season_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT p.player_id, p.surname, p.name
            FROM player p
            WHERE p.player_id NOT IN (
                SELECT player_id FROM player_season WHERE season_id = ?
            )
            ORDER BY p.surname COLLATE NOCASE, p.name COLLATE NOCASE
            """,
            (season_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def insert_player_season(player_id: int, season_id: int, user_id: int) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO player_season (player_id, season_id)
            VALUES (?, ?)
            """,
            (player_id, season_id),
        )
        ps_id = int(cur.lastrowid)
        _audit(
            conn,
            "player_season",
            ps_id,
            "INSERT",
            user_id,
            {"player_id": player_id, "season_id": season_id},
        )
        conn.commit()
        return ps_id


def fetch_player_season(player_season_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT ps.player_season_id, ps.player_id, ps.season_id,
                   p.surname, p.name,
                   s.start_year, s.end_year
            FROM player_season ps
            JOIN player p ON p.player_id = ps.player_id
            JOIN season s ON s.season_id = ps.season_id
            WHERE ps.player_season_id = ?
            """,
            (player_season_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_roster_stints(player_season_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT rs.roster_stint_id, rs.player_season_id, rs.club_id,
                   rs.start_date, rs.end_date, rs.enabled, rs.jersey_number,
                   c.name AS club_name
            FROM roster_stint rs
            JOIN club c ON c.club_id = rs.club_id
            WHERE rs.player_season_id = ?
            ORDER BY rs.start_date ASC, rs.roster_stint_id ASC
            """,
            (player_season_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def parse_iso_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def fetch_roster_stint_player_season_id(roster_stint_id: int) -> int | None:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT player_season_id FROM roster_stint WHERE roster_stint_id = ?",
            (roster_stint_id,),
        )
        row = cur.fetchone()
        return int(row["player_season_id"]) if row else None


def insert_roster_stint(
    player_season_id: int,
    club_id: int,
    start_date: str,
    jersey_number: str | None,
    user_id: int,
) -> int:
    new_start = parse_iso_date(start_date)
    jersey = (jersey_number or "").strip() or None

    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT roster_stint_id, start_date, end_date
            FROM roster_stint
            WHERE player_season_id = ? AND enabled = 1 AND end_date IS NULL
            """,
            (player_season_id,),
        )
        open_rows = cur.fetchall()
        if len(open_rows) > 1:
            raise ValueError(
                "More than one open stint exists for this enrollment; fix the data first."
            )
        prev_end = new_start - timedelta(days=1)
        for row in open_rows:
            old_start = parse_iso_date(row["start_date"])
            if prev_end < old_start:
                raise ValueError(
                    "New stint would end the previous one before it started; "
                    "choose a later start date or close the current stint manually."
                )
            conn.execute(
                "UPDATE roster_stint SET end_date = ? WHERE roster_stint_id = ?",
                (prev_end.isoformat(), row["roster_stint_id"]),
            )
            _audit(
                conn,
                "roster_stint",
                int(row["roster_stint_id"]),
                "UPDATE",
                user_id,
                {"field": "end_date", "value": prev_end.isoformat(), "reason": "new_stint"},
            )

        cur = conn.execute(
            """
            INSERT INTO roster_stint (player_season_id, club_id, start_date, end_date, enabled, jersey_number)
            VALUES (?, ?, ?, NULL, 1, ?)
            """,
            (player_season_id, club_id, new_start.isoformat(), jersey),
        )
        rid = int(cur.lastrowid)
        _audit(
            conn,
            "roster_stint",
            rid,
            "INSERT",
            user_id,
            {
                "player_season_id": player_season_id,
                "club_id": club_id,
                "start_date": new_start.isoformat(),
                "jersey_number": jersey,
            },
        )
        conn.commit()
        return rid


def end_roster_stint(roster_stint_id: int, end_date: str, user_id: int) -> None:
    end_d = parse_iso_date(end_date)
    with _connect() as conn:
        cur = conn.execute(
            "SELECT start_date, end_date FROM roster_stint WHERE roster_stint_id = ?",
            (roster_stint_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("Stint not found.")
        if row["end_date"] is not None:
            raise ValueError("Stint already ended.")
        start_d = parse_iso_date(row["start_date"])
        if end_d < start_d:
            raise ValueError("End date cannot be before start date.")
        conn.execute(
            "UPDATE roster_stint SET end_date = ? WHERE roster_stint_id = ?",
            (end_d.isoformat(), roster_stint_id),
        )
        _audit(
            conn,
            "roster_stint",
            roster_stint_id,
            "UPDATE",
            user_id,
            {"field": "end_date", "value": end_d.isoformat()},
        )
        conn.commit()


def set_roster_stint_enabled(roster_stint_id: int, enabled: bool, user_id: int) -> None:
    v = 1 if enabled else 0
    with _connect() as conn:
        conn.execute(
            "UPDATE roster_stint SET enabled = ? WHERE roster_stint_id = ?",
            (v, roster_stint_id),
        )
        _audit(
            conn,
            "roster_stint",
            roster_stint_id,
            "UPDATE",
            user_id,
            {"field": "enabled", "value": enabled},
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
