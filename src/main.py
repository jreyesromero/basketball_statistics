from datetime import date, datetime
from pathlib import Path
from typing import Any

import sqlite3
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Project root (parent of src/) — schema.sql and data/ live here.
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DB_PATH = ROOT_DIR / "data" / "basket.sqlite"
SCHEMA_PATH = ROOT_DIR / "schema.sql"

templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))


def _dob_max_input_value() -> str:
    return date.today().isoformat()


app = FastAPI(title="Basketball statistics")
app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")


_CLUB_DDL = """
CREATE TABLE IF NOT EXISTS club (
  club_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT NOT NULL,
  foundation_date  TEXT NOT NULL,
  address          TEXT
);
CREATE INDEX IF NOT EXISTS idx_club_name ON club (name COLLATE NOCASE);
"""


def _ensure_club_table() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(_CLUB_DDL)


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql)
    _ensure_club_table()


def fetch_players() -> list[dict[str, Any]]:
    try:
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
    except sqlite3.Error:
        return []


def fetch_clubs() -> list[dict[str, Any]]:
    try:
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
    except sqlite3.Error:
        return []


@app.on_event("startup")
def _startup() -> None:
    ensure_database()


@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "welcome.html", {})


@app.get("/players/management", response_class=HTMLResponse)
async def players_management(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "players_management.html", {})


@app.get("/clubs/management", response_class=HTMLResponse)
async def clubs_management(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "clubs_management.html", {})


@app.get("/players/new", response_class=HTMLResponse)
async def add_player_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "add_player.html",
        {
            "error": None,
            "values": {},
            "max_dob": _dob_max_input_value(),
        },
    )


@app.get("/players/remove", response_class=HTMLResponse)
async def remove_players_form(
    request: Request,
    removed: int | None = Query(None, ge=0),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "remove_players.html",
        {
            "players": fetch_players(),
            "error": None,
            "removed_count": removed,
        },
    )


@app.post("/players/remove", response_model=None)
async def remove_players_submit(request: Request) -> RedirectResponse | HTMLResponse:
    form = await request.form()
    raw_ids = form.getlist("player_id")
    ids: list[int] = []
    for x in raw_ids:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue

    if not ids:
        return templates.TemplateResponse(
            request,
            "remove_players.html",
            {
                "players": fetch_players(),
                "error": "Select at least one player to remove.",
                "removed_count": None,
            },
            status_code=422,
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"DELETE FROM player WHERE player_id IN ({placeholders})",
                ids,
            )
            conn.commit()
            deleted = cur.rowcount
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "remove_players.html",
            {
                "players": fetch_players(),
                "error": "Could not update the database. Try again.",
                "removed_count": None,
            },
            status_code=500,
        )

    return RedirectResponse(
        url=f"/players/remove?removed={deleted}",
        status_code=303,
    )


@app.get("/players", response_class=HTMLResponse)
async def list_players(
    request: Request,
    success: str | None = Query(None),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "players_list.html",
        {
            "success": success == "1",
            "players": fetch_players(),
        },
    )


@app.post("/players", response_model=None)
async def create_player(
    request: Request,
    name: str = Form(...),
    surname: str = Form(...),
    address: str = Form(""),
    date_of_birth: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    name_t = name.strip()
    surname_t = surname.strip()
    address_t = address.strip() or None
    dob_t = date_of_birth.strip()

    values = {
        "name": name_t,
        "surname": surname_t,
        "address": address.strip(),
        "date_of_birth": dob_t,
    }

    if not name_t or not surname_t:
        return templates.TemplateResponse(
            request,
            "add_player.html",
            {
                "error": "Name and surname are required.",
                "values": values,
                "max_dob": _dob_max_input_value(),
            },
            status_code=422,
        )

    try:
        dob_parsed = datetime.strptime(dob_t, "%Y-%m-%d").date()
    except ValueError:
        return templates.TemplateResponse(
            request,
            "add_player.html",
            {
                "error": "Date of birth must be a valid date in YYYY-MM-DD format.",
                "values": values,
                "max_dob": _dob_max_input_value(),
            },
            status_code=422,
        )

    if dob_parsed > date.today():
        return templates.TemplateResponse(
            request,
            "add_player.html",
            {
                "error": "Date of birth cannot be in the future.",
                "values": values,
                "max_dob": _dob_max_input_value(),
            },
            status_code=422,
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO player (name, surname, address, date_of_birth)
                VALUES (?, ?, ?, ?)
                """,
                (name_t, surname_t, address_t, dob_t),
            )
            conn.commit()
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "add_player.html",
            {
                "error": "Could not save to the database. Try again.",
                "values": values,
                "max_dob": _dob_max_input_value(),
            },
            status_code=500,
        )

    return RedirectResponse(url="/players?success=1", status_code=303)


@app.get("/clubs/new", response_class=HTMLResponse)
async def add_club_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "add_club.html",
        {
            "error": None,
            "values": {},
            "max_foundation": _dob_max_input_value(),
        },
    )


@app.get("/clubs/remove", response_class=HTMLResponse)
async def remove_clubs_form(
    request: Request,
    removed: int | None = Query(None, ge=0),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "remove_clubs.html",
        {
            "clubs": fetch_clubs(),
            "error": None,
            "removed_count": removed,
        },
    )


@app.post("/clubs/remove", response_model=None)
async def remove_clubs_submit(request: Request) -> RedirectResponse | HTMLResponse:
    form = await request.form()
    raw_ids = form.getlist("club_id")
    ids: list[int] = []
    for x in raw_ids:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue

    if not ids:
        return templates.TemplateResponse(
            request,
            "remove_clubs.html",
            {
                "clubs": fetch_clubs(),
                "error": "Select at least one club to remove.",
                "removed_count": None,
            },
            status_code=422,
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"DELETE FROM club WHERE club_id IN ({placeholders})",
                ids,
            )
            conn.commit()
            deleted = cur.rowcount
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "remove_clubs.html",
            {
                "clubs": fetch_clubs(),
                "error": "Could not update the database. Try again.",
                "removed_count": None,
            },
            status_code=500,
        )

    return RedirectResponse(
        url=f"/clubs/remove?removed={deleted}",
        status_code=303,
    )


@app.get("/clubs", response_class=HTMLResponse)
async def list_clubs(
    request: Request,
    success: str | None = Query(None),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "clubs_list.html",
        {
            "success": success == "1",
            "clubs": fetch_clubs(),
        },
    )


@app.post("/clubs", response_model=None)
async def create_club(
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    foundation_date: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    name_t = name.strip()
    address_t = address.strip() or None
    fd_t = foundation_date.strip()

    values = {
        "name": name_t,
        "address": address.strip(),
        "foundation_date": fd_t,
    }

    if not name_t:
        return templates.TemplateResponse(
            request,
            "add_club.html",
            {
                "error": "Club name is required.",
                "values": values,
                "max_foundation": _dob_max_input_value(),
            },
            status_code=422,
        )

    try:
        fd_parsed = datetime.strptime(fd_t, "%Y-%m-%d").date()
    except ValueError:
        return templates.TemplateResponse(
            request,
            "add_club.html",
            {
                "error": "Foundation date must be a valid date in YYYY-MM-DD format.",
                "values": values,
                "max_foundation": _dob_max_input_value(),
            },
            status_code=422,
        )

    if fd_parsed > date.today():
        return templates.TemplateResponse(
            request,
            "add_club.html",
            {
                "error": "Foundation date cannot be in the future.",
                "values": values,
                "max_foundation": _dob_max_input_value(),
            },
            status_code=422,
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO club (name, address, foundation_date)
                VALUES (?, ?, ?)
                """,
                (name_t, address_t, fd_t),
            )
            conn.commit()
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "add_club.html",
            {
                "error": "Could not save to the database. Try again.",
                "values": values,
                "max_foundation": _dob_max_input_value(),
            },
            status_code=500,
        )

    return RedirectResponse(url="/clubs?success=1", status_code=303)
