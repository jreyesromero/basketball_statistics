"""User accounts (SQLite)."""

from typing import Any

import sqlite3

from src.db_paths import DB_PATH


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    d["is_admin"] = bool(d.get("is_admin", 0))
    return d


def fetch_user_by_id(user_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT user_id, email, password_hash, is_active, is_admin, created_at
                FROM users WHERE user_id = ?
                """,
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
                """
                SELECT user_id, email, password_hash, is_active, is_admin, created_at
                FROM users WHERE email = ?
                """,
                (normalized,),
            )
            row = cur.fetchone()
            return _row_to_user(row) if row else None
    except sqlite3.Error:
        return None


def count_users() -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM users")
            return int(cur.fetchone()[0])
    except sqlite3.Error:
        return 0


def list_all_users() -> list[dict[str, Any]]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT user_id, email, password_hash, is_active, is_admin, created_at
                FROM users
                ORDER BY email COLLATE NOCASE
                """
            )
            return [_row_to_user(row) for row in cur.fetchall()]
    except sqlite3.Error:
        return []


def count_active_admins() -> int:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1 AND is_active = 1"
            )
            return int(cur.fetchone()[0])
    except sqlite3.Error:
        return 0


def sole_active_admin_user_id() -> int | None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute(
                """
                SELECT user_id FROM users
                WHERE is_admin = 1 AND is_active = 1
                """
            )
            rows = cur.fetchall()
            if len(rows) == 1:
                return int(rows[0][0])
            return None
    except sqlite3.Error:
        return None


def insert_user(
    email: str,
    password_hash: str,
    *,
    is_active: bool = True,
    is_admin: bool = False,
) -> int:
    normalized = email.strip().lower()
    active_int = 1 if is_active else 0
    admin_int = 1 if is_admin else 0
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, is_active, is_admin)
            VALUES (?, ?, ?, ?)
            """,
            (normalized, password_hash, active_int, admin_int),
        )
        conn.commit()
        return int(cur.lastrowid)


def set_user_active(user_id: int, *, active: bool) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET is_active = ? WHERE user_id = ?",
            (1 if active else 0, user_id),
        )
        conn.commit()


def set_user_admin(user_id: int, *, admin: bool) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET is_admin = ? WHERE user_id = ?",
            (1 if admin else 0, user_id),
        )
        conn.commit()


def delete_user(user_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()


def update_password_hash(user_id: int, password_hash: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE user_id = ?",
            (password_hash, user_id),
        )
        conn.commit()
