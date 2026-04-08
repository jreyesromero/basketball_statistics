"""User accounts (SQLite)."""

from typing import Any

import sqlite3

from src.db_paths import DB_PATH


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    return d


def fetch_user_by_id(user_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT user_id, email, password_hash, is_active, created_at FROM users WHERE user_id = ?",
                (user_id,),
            )
            row = cur.fetchone()
            return _row_to_user(row) if row else None
    except sqlite3.Error:
        return None


def fetch_user_by_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT user_id, email, password_hash, is_active, created_at FROM users WHERE email = ?",
                (normalized,),
            )
            row = cur.fetchone()
            return _row_to_user(row) if row else None
    except sqlite3.Error:
        return None


def insert_user(email: str, password_hash: str, *, is_active: bool = True) -> int:
    normalized = email.strip().lower()
    active_int = 1 if is_active else 0
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, is_active)
            VALUES (?, ?, ?)
            """,
            (normalized, password_hash, active_int),
        )
        conn.commit()
        return int(cur.lastrowid)
