"""Password reset token storage and password update."""

from __future__ import annotations

import sqlite3

import pytest

from tests.conftest import init_sqlite_schema


@pytest.fixture
def pwd_db(tmp_path, monkeypatch):
    db_path = tmp_path / "pwd_reset.sqlite"
    init_sqlite_schema(db_path)
    monkeypatch.setattr("src.users_repo.DB_PATH", db_path)
    monkeypatch.setattr("src.password_reset_repo.DB_PATH", db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            ("reset-me@example.com", "not-a-real-hash"),
        )
        conn.commit()
    return db_path


def test_issue_and_consume_token(pwd_db):
    from src import password_reset_repo
    from src.passwords import hash_password, verify_password
    from src.users_repo import fetch_user_by_email, update_password_hash

    user = fetch_user_by_email("reset-me@example.com")
    assert user is not None
    uid = user["user_id"]

    raw = password_reset_repo.issue_reset_token(uid)
    assert len(raw) > 20
    row = password_reset_repo.lookup_valid_reset(raw)
    assert row is not None
    assert int(row["user_id"]) == uid

    new_hash = hash_password("new-secret-8")
    update_password_hash(uid, new_hash)
    password_reset_repo.mark_reset_used(int(row["reset_id"]))

    assert password_reset_repo.lookup_valid_reset(raw) is None
    u2 = fetch_user_by_email("reset-me@example.com")
    assert verify_password(u2["password_hash"], "new-secret-8")


def test_new_token_invalidates_previous(pwd_db):
    from src import password_reset_repo

    raw1 = password_reset_repo.issue_reset_token(1)
    raw2 = password_reset_repo.issue_reset_token(1)
    assert password_reset_repo.lookup_valid_reset(raw1) is None
    assert password_reset_repo.lookup_valid_reset(raw2) is not None
