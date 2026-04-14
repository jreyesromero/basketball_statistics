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
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    r2 = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
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
        follow_redirects=False,
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
        follow_redirects=False,
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
        follow_redirects=False,
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

    r1 = c.post(
        "/seasons/new",
        data={"start_year": "2030", "end_year": "2031"},
        follow_redirects=False,
    )
    assert r1.status_code == 303
    r2 = c.post("/seasons/new", data={"start_year": "2030", "end_year": "2031"})
    assert r2.status_code == 422
    assert "already exists" in r2.text


def test_clubs_list_shows_season_roster_dropdown_after_team_added(client):
    """Clubs table gets season roster <select> linking to /season-team/{id}."""
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    c.post(
        "/clubs",
        data={
            "name": "Roster City BC",
            "address": "",
            "foundation_date": "2000-01-01",
        },
        follow_redirects=False,
    )
    r_season = c.post(
        "/seasons/new",
        data={"start_year": "2025", "end_year": "2026"},
        follow_redirects=False,
    )
    assert r_season.status_code == 303
    m = re.search(r"/seasons/(\d+)$", r_season.headers.get("location", ""))
    assert m
    season_id = int(m.group(1))

    r_add = c.post(
        f"/seasons/{season_id}/add-team",
        data={"club_id": "1"},
        follow_redirects=False,
    )
    assert r_add.status_code == 303

    listing = c.get("/clubs")
    assert listing.status_code == 200
    assert "club-roster-season-select" in listing.text
    assert "Roster City BC" in listing.text
    assert "2025" in listing.text and "2026" in listing.text
    assert re.search(r'/season-team/\d+', listing.text)


def test_season_team_detail_page(client):
    c, db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    c.post(
        "/clubs",
        data={
            "name": "Detail Club",
            "address": "",
            "foundation_date": "1999-05-05",
        },
        follow_redirects=False,
    )
    r_season = c.post(
        "/seasons/new",
        data={"start_year": "2024", "end_year": "2025"},
        follow_redirects=False,
    )
    season_id = int(re.search(r"/seasons/(\d+)$", r_season.headers["location"]).group(1))
    c.post(
        f"/seasons/{season_id}/add-team",
        data={"club_id": "1"},
        follow_redirects=False,
    )
    with sqlite3.connect(db_path) as conn:
        st_id = conn.execute(
            "SELECT season_team_id FROM season_team WHERE club_id = 1"
        ).fetchone()[0]

    page = c.get(f"/season-team/{st_id}")
    assert page.status_code == 200
    assert "Detail Club" in page.text
    assert "2024" in page.text and "2025" in page.text
    assert "Add player" in page.text


def test_team_management_legacy_url_redirects_to_season(client):
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    r_season = c.post(
        "/seasons/new",
        data={"start_year": "2099", "end_year": "2100"},
        follow_redirects=False,
    )
    season_id = int(re.search(r"/seasons/(\d+)$", r_season.headers["location"]).group(1))

    r = c.get(
        f"/seasons/{season_id}/team-management",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location", "").endswith(f"/seasons/{season_id}")


def test_season_detail_shows_team_jump_and_open_roster_links(client):
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    c.post(
        "/clubs",
        data={
            "name": "Jump Club",
            "address": "",
            "foundation_date": "2010-01-01",
        },
        follow_redirects=False,
    )
    r_season = c.post(
        "/seasons/new",
        data={"start_year": "2018", "end_year": "2019"},
        follow_redirects=False,
    )
    season_id = int(re.search(r"/seasons/(\d+)$", r_season.headers["location"]).group(1))
    c.post(
        f"/seasons/{season_id}/add-team",
        data={"club_id": "1"},
        follow_redirects=False,
    )

    page = c.get(f"/seasons/{season_id}")
    assert page.status_code == 200
    assert "season-team-jump-select" in page.text
    assert "Go to team roster" in page.text
    assert "Open roster" in page.text
    assert "Jump Club" in page.text
    assert re.search(r"/season-team/\d+", page.text)


def test_seasons_list_shows_team_count_column(client):
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    c.post(
        "/clubs",
        data={"name": "Count Club", "address": "", "foundation_date": "2005-01-01"},
        follow_redirects=False,
    )
    r_season = c.post(
        "/seasons/new",
        data={"start_year": "3010", "end_year": "3011"},
        follow_redirects=False,
    )
    season_id = int(re.search(r"/seasons/(\d+)$", r_season.headers["location"]).group(1))

    listing = c.get("/seasons")
    assert listing.status_code == 200
    assert "Teams" in listing.text
    assert ">0<" in listing.text or "0</td>" in listing.text

    c.post(
        f"/seasons/{season_id}/add-team",
        data={"club_id": "1"},
        follow_redirects=False,
    )
    listing2 = c.get("/seasons")
    assert listing2.status_code == 200
    assert "3010" in listing2.text and "3011" in listing2.text
    assert ">1<" in listing2.text or "1</td>" in listing2.text


def test_assign_player_via_form_redirects_to_team_detail(client):
    c, db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    c.post(
        "/clubs",
        data={"name": "Assign FC", "address": "", "foundation_date": "2012-12-12"},
        follow_redirects=False,
    )
    c.post(
        "/players",
        data={
            "name": "Pat",
            "surname": "Assignee",
            "address": "",
            "date_of_birth": "2002-02-02",
        },
        follow_redirects=False,
    )
    r_season = c.post(
        "/seasons/new",
        data={"start_year": "3020", "end_year": "3021"},
        follow_redirects=False,
    )
    season_id = int(re.search(r"/seasons/(\d+)$", r_season.headers["location"]).group(1))
    c.post(
        f"/seasons/{season_id}/add-team",
        data={"club_id": "1"},
        follow_redirects=False,
    )
    with sqlite3.connect(db_path) as conn:
        st_id = conn.execute(
            "SELECT season_team_id FROM season_team LIMIT 1"
        ).fetchone()[0]

    r = c.post(
        f"/season-team/{st_id}/assign-player",
        data={"player_id": "1", "jersey_number": "99"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers.get("location", "").endswith(f"/season-team/{st_id}")

    team_page = c.get(f"/season-team/{st_id}")
    assert team_page.status_code == 200
    assert "Assignee" in team_page.text
    assert "99" in team_page.text


def test_clubs_list_only_teams_in_season_get_roster_select(client):
    """Clubs with no season_team row show em dash, not a season roster <select>."""
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    c.post(
        "/clubs",
        data={"name": "In Season", "address": "", "foundation_date": "2000-01-01"},
        follow_redirects=False,
    )
    c.post(
        "/clubs",
        data={"name": "Orphan Club", "address": "", "foundation_date": "2001-01-01"},
        follow_redirects=False,
    )
    r_season = c.post(
        "/seasons/new",
        data={"start_year": "3030", "end_year": "3031"},
        follow_redirects=False,
    )
    season_id = int(re.search(r"/seasons/(\d+)$", r_season.headers["location"]).group(1))
    c.post(
        f"/seasons/{season_id}/add-team",
        data={"club_id": "1"},
        follow_redirects=False,
    )

    listing = c.get("/clubs")
    assert listing.status_code == 200
    # Class name also appears inside <script> querySelectorAll; count real <select> only.
    assert listing.text.count('class="club-roster-season-select"') == 1
    assert "In Season" in listing.text
    assert "Orphan Club" in listing.text


def test_admin_audit_log_page_ok(client):
    c, _db_path = client
    _bootstrap_and_login(c, "admin@example.com", "adminpass1")

    r = c.get("/admin/audit-log")
    assert r.status_code == 200
    assert "Audit log" in r.text


def test_forgot_password_post_redirects_with_sent_query(client, monkeypatch):
    def _noop_send(_to: str, _url: str) -> None:
        return None

    monkeypatch.setattr("src.main.send_password_reset_email", _noop_send)

    c, _db_path = client
    c.post(
        "/bootstrap",
        data={
            "email": "fp@example.com",
            "password": "longpass12",
            "password_confirm": "longpass12",
        },
        follow_redirects=False,
    )

    r = c.post(
        "/forgot-password",
        data={"email": "fp@example.com"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "sent=1" in (r.headers.get("location") or "")


def test_reset_password_page_rejects_bad_token(client):
    c, _db_path = client
    c.post(
        "/bootstrap",
        data={
            "email": "rt@example.com",
            "password": "longpass12",
            "password_confirm": "longpass12",
        },
        follow_redirects=False,
    )

    r = c.get("/reset-password", params={"token": "not-a-valid-token"})
    assert r.status_code == 422
    assert "invalid" in r.text.lower() or "expired" in r.text.lower()
