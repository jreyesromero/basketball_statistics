"""One-time password reset tokens (SQLite)."""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

import sqlite3

from src.db_paths import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_reset_token(user_id: int) -> str:
    """Invalidate pending tokens for user, insert new row, return raw token (for email only)."""
    raw = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw)
    with _connect() as conn:
        conn.execute(
            "DELETE FROM password_reset WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO password_reset (user_id, token_hash, expires_at)
            VALUES (?, ?, datetime('now', '+1 hour'))
            """,
            (user_id, token_hash),
        )
        conn.commit()
    return raw


def lookup_valid_reset(raw_token: str) -> dict[str, Any] | None:
    """Return reset_id and user_id if token is valid and not expired."""
    th = hash_reset_token(raw_token.strip())
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT reset_id, user_id
            FROM password_reset
            WHERE token_hash = ?
              AND used_at IS NULL
              AND datetime(expires_at) > datetime('now')
            """,
            (th,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def mark_reset_used(reset_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE password_reset SET used_at = datetime('now') WHERE reset_id = ?",
            (reset_id,),
        )
        conn.commit()


def delete_pending_resets_for_user(user_id: int) -> None:
    """Remove unused tokens (e.g. after failed email delivery)."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM password_reset WHERE user_id = ? AND used_at IS NULL",
            (user_id,),
        )
        conn.commit()
