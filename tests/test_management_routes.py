"""Integration tests: create player, club, and season via HTML forms (logged-in user)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _patch_all_db_paths(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    for mod in (
        "src.main",
        "src.users_repo",
        "src.queries",
        "src.roster_repo",
        "src.password_reset_repo",
    ):
        monkeypatch.setattr(f"{mod}.DB_PATH", db_path)


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "management.sqlite"
    _patch_all_db_paths(monkeypatch, db_path)
    from src.main import app

    with TestClient(app) as c:
        yield c, db_path


def _bootstrap_and_login(client: TestClient, email: str, password: str) -> None:
    r = client.post(
        "/bootstrap",
        data={
            "email": email,
            "password": password,
            "password_confirm": password,
        },
    )
    assert r.status_code == 303, r.text
    r2 = client.post("/login", data={"email": email, "password": password})
    assert r2.status_code == 303, r2.text


def test_create_player_via_post(client):
    c, db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    r = c.post(
        "/players",
        data={
            "name": "Jamie",
            "surname": "Hoops",
            "address": "1 Court St",
            "date_of_birth": "2001-03-15",
        },
    )
    assert r.status_code == 303
    assert r.headers.get("location", "").startswith("/players?success=1")

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT name, surname, date_of_birth FROM player WHERE surname = ?",
            ("Hoops",),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "Jamie"
    assert row[1] == "Hoops"
    assert row[2] == "2001-03-15"

    listing = c.get("/players")
    assert listing.status_code == 200
    assert "Jamie" in listing.text
    assert "Hoops" in listing.text


def test_create_club_via_post(client):
    c, db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    r = c.post(
        "/clubs",
        data={
            "name": "Downtown Hoopers",
            "address": "Arena Rd",
            "foundation_date": "1988-11-20",
        },
    )
    assert r.status_code == 303
    assert r.headers.get("location", "").startswith("/clubs?success=1")

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT name, foundation_date, address FROM club WHERE name = ?",
            ("Downtown Hoopers",),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == "Downtown Hoopers"
    assert row[1] == "1988-11-20"
    assert row[2] == "Arena Rd"

    listing = c.get("/clubs")
    assert listing.status_code == 200
    assert "Downtown Hoopers" in listing.text


def test_create_season_via_post(client):
    c, db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    r = c.post(
        "/seasons/new",
        data={"start_year": "2025", "end_year": "2026"},
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    m = re.match(r".*/seasons/(\d+)$", loc)
    assert m, f"unexpected Location: {loc!r}"
    season_id = int(m.group(1))

    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "SELECT start_year, end_year FROM season WHERE season_id = ?",
            (season_id,),
        )
        row = cur.fetchone()
    assert row == ("2025", "2026")

    detail = c.get(f"/seasons/{season_id}")
    assert detail.status_code == 200
    assert "2025" in detail.text and "2026" in detail.text


def test_create_season_duplicate_returns_422(client):
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    r1 = c.post("/seasons/new", data={"start_year": "2030", "end_year": "2031"})
    assert r1.status_code == 303
    r2 = c.post("/seasons/new", data={"start_year": "2030", "end_year": "2031"})
    assert r2.status_code == 422
    assert "already exists" in r2.text
