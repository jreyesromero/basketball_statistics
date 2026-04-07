"""Read-only database access shared by HTML routes and the JSON API."""

from typing import Any

import sqlite3

from src.db_paths import DB_PATH


def load_players() -> list[dict[str, Any]]:
    """Load all players; raises sqlite3.Error on database failure."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT player_id, name, surname, address, date_of_birth
            FROM player
            ORDER BY surname COLLATE NOCASE, name COLLATE NOCASE
            """
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_players() -> list[dict[str, Any]]:
    try:
        return load_players()
    except sqlite3.Error:
        return []


def load_clubs() -> list[dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT club_id, name, address, foundation_date
            FROM club
            ORDER BY name COLLATE NOCASE
            """
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_clubs() -> list[dict[str, Any]]:
    try:
        return load_clubs()
    except sqlite3.Error:
        return []
