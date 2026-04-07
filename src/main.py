from datetime import datetime
from pathlib import Path

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

app = FastAPI(title="Basket")
app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql)


@app.on_event("startup")
def _startup() -> None:
    ensure_database()


@app.get("/", response_class=HTMLResponse)
async def add_player_form(
    request: Request,
    success: str | None = Query(None),
    error: str | None = Query(None),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "add_player.html",
        {
            "success": success == "1",
            "error": error,
            "values": {},
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
                "success": False,
                "error": "Name and surname are required.",
                "values": values,
            },
            status_code=422,
        )

    try:
        datetime.strptime(dob_t, "%Y-%m-%d")
    except ValueError:
        return templates.TemplateResponse(
            request,
            "add_player.html",
            {
                "success": False,
                "error": "Date of birth must be a valid date in YYYY-MM-DD format.",
                "values": values,
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
                "success": False,
                "error": "Could not save to the database. Try again.",
                "values": values,
            },
            status_code=500,
        )

    return RedirectResponse(url="/?success=1", status_code=303)
