from datetime import date, datetime
import os
import sys

import sqlite3
from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from src.api.clubs import router as clubs_api_router
from src.api.players import router as players_api_router
from src.db_paths import DB_PATH, SCHEMA_PATH, SRC_DIR
from src.middleware_auth import RequireLoginMiddleware
from src.passwords import hash_password, verify_password
from src.queries import fetch_clubs, fetch_players
from src.users_repo import fetch_user_by_email, fetch_user_by_id, insert_user

_SESSION_SECRET = os.environ.get("BASKET_SESSION_SECRET", "").strip()
if len(_SESSION_SECRET) < 32:
    print(
        "ERROR: BASKET_SESSION_SECRET must be set to at least 32 characters.\n"
        "Example: export BASKET_SESSION_SECRET=$(openssl rand -hex 32)\n"
        "Or run via bin/run.sh, which generates one if unset.",
        file=sys.stderr,
    )
    sys.exit(1)

templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))


def _dob_max_input_value() -> str:
    return date.today().isoformat()


def _plausible_email(value: str) -> bool:
    s = value.strip()
    if not s or len(s) > 254 or " " in s or s.count("@") != 1:
        return False
    local, domain = s.split("@", 1)
    return bool(local) and bool(domain) and "." in domain


app = FastAPI(title="Basketball statistics")
app.add_middleware(RequireLoginMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    max_age=60 * 60 * 24 * 14,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")
app.include_router(players_api_router, prefix="/api")
app.include_router(clubs_api_router, prefix="/api")


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


_USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
  user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash  TEXT NOT NULL,
  is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email COLLATE NOCASE);
"""


def _ensure_users_table() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(_USERS_DDL)


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql)
    _ensure_club_table()
    _ensure_users_table()


@app.on_event("startup")
def _startup() -> None:
    ensure_database()


@app.get("/login", response_class=HTMLResponse, response_model=None)
async def login_page(
    request: Request,
    registered: str | None = Query(None),
):
    uid = request.session.get("user_id")
    if uid is not None:
        try:
            existing = fetch_user_by_id(int(uid))
        except (TypeError, ValueError):
            existing = None
        if existing is not None and existing["is_active"]:
            return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": None,
            "values": {},
            "registered_ok": registered == "1",
        },
    )


@app.post("/login", response_model=None)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    email_t = email.strip()
    values = {"email": email_t}
    if not _plausible_email(email_t):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Enter a valid email address.",
                "values": values,
                "registered_ok": False,
            },
            status_code=422,
        )
    user = fetch_user_by_email(email_t)
    if user is None or not verify_password(user["password_hash"], password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Invalid email or password.",
                "values": values,
                "registered_ok": False,
            },
            status_code=422,
        )
    if not user["is_active"]:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "This account has been disabled.",
                "values": values,
                "registered_ok": False,
            },
            status_code=403,
        )
    request.session["user_id"] = user["user_id"]
    return RedirectResponse(url="/", status_code=303)


@app.get("/register", response_class=HTMLResponse, response_model=None)
async def register_page(request: Request):
    uid = request.session.get("user_id")
    if uid is not None:
        try:
            existing = fetch_user_by_id(int(uid))
        except (TypeError, ValueError):
            existing = None
        if existing is not None and existing["is_active"]:
            return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request,
        "register.html",
        {"error": None, "values": {}},
    )


@app.post("/register", response_model=None)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
) -> RedirectResponse | HTMLResponse:
    email_t = email.strip()
    values = {"email": email_t}
    if not _plausible_email(email_t):
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Enter a valid email address.", "values": values},
            status_code=422,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Password must be at least 8 characters.", "values": values},
            status_code=422,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Passwords do not match.", "values": values},
            status_code=422,
        )
    try:
        insert_user(email_t, hash_password(password), is_active=True)
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "error": "An account with this email already exists.",
                "values": values,
            },
            status_code=422,
        )
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "error": "Could not create the account. Try again.",
                "values": values,
            },
            status_code=500,
        )
    return RedirectResponse(url="/login?registered=1", status_code=303)


@app.post("/logout", response_model=None)
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


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
