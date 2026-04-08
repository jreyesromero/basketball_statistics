"""Tests for src.users_repo with an isolated SQLite file."""

import sqlite3

import pytest

import src.users_repo as users_repo
from src.passwords import hash_password
from tests.conftest import init_sqlite_schema


@pytest.fixture
def user_db(monkeypatch, tmp_path):
    db_path = tmp_path / "users.sqlite"
    monkeypatch.setattr(users_repo, "DB_PATH", db_path)
    init_sqlite_schema(db_path)
    return db_path


def test_insert_and_fetch_by_email(user_db) -> None:
    uid = users_repo.insert_user(
        "alice@example.com",
        hash_password("password123"),
        is_active=True,
        is_admin=False,
    )
    assert uid >= 1
    row = users_repo.fetch_user_by_email("Alice@Example.com")
    assert row is not None
    assert row["user_id"] == uid
    assert row["email"] == "alice@example.com"
    assert row["is_active"] is True
    assert row["is_admin"] is False


def test_fetch_user_by_id(user_db) -> None:
    uid = users_repo.insert_user(
        "bob@example.com",
        hash_password("x"),
        is_active=True,
        is_admin=True,
    )
    row = users_repo.fetch_user_by_id(uid)
    assert row is not None
    assert row["email"] == "bob@example.com"
    assert row["is_admin"] is True


def test_count_users(user_db) -> None:
    assert users_repo.count_users() == 0
    users_repo.insert_user("a@a.com", hash_password("p"), is_active=True, is_admin=False)
    assert users_repo.count_users() == 1


def test_list_all_users_sorted_by_email(user_db) -> None:
    users_repo.insert_user("z@z.com", hash_password("1"), is_active=True, is_admin=False)
    users_repo.insert_user("a@a.com", hash_password("2"), is_active=True, is_admin=False)
    rows = users_repo.list_all_users()
    assert [r["email"] for r in rows] == ["a@a.com", "z@z.com"]


def test_set_user_active(user_db) -> None:
    uid = users_repo.insert_user("c@c.com", hash_password("p"), is_active=True, is_admin=False)
    users_repo.set_user_active(uid, active=False)
    row = users_repo.fetch_user_by_id(uid)
    assert row is not None
    assert row["is_active"] is False


def test_delete_user(user_db) -> None:
    uid = users_repo.insert_user("d@d.com", hash_password("p"), is_active=True, is_admin=False)
    users_repo.delete_user(uid)
    assert users_repo.fetch_user_by_id(uid) is None


def test_insert_duplicate_email_raises(user_db) -> None:
    users_repo.insert_user("e@e.com", hash_password("p"), is_active=True, is_admin=False)
    with pytest.raises(sqlite3.IntegrityError):
        users_repo.insert_user("e@e.com", hash_password("q"), is_active=True, is_admin=False)
