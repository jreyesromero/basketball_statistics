"""Seasons, enrollments, and roster stints (HTML UI)."""

from datetime import date

import sqlite3
from fastapi import APIRouter, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.db_paths import SRC_DIR
from src.queries import fetch_clubs
from src import roster_repo

templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))

router = APIRouter(tags=["roster"])


def _current_user_id(request: Request) -> int:
    return int(request.state.current_user["user_id"])


@router.get("/seasons", response_class=HTMLResponse, response_model=None)
async def seasons_list(request: Request):
    seasons = roster_repo.list_seasons()
    return templates.TemplateResponse(
        request,
        "seasons_list.html",
        {"seasons": seasons, "error": None},
    )


@router.get("/seasons/new", response_class=HTMLResponse, response_model=None)
async def season_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "season_new.html",
        {"error": None, "values": {}},
    )


@router.post("/seasons/new", response_model=None)
async def season_create(
    request: Request,
    start_year: str = Form(...),
    end_year: str = Form(...),
):
    sy, ey = start_year.strip(), end_year.strip()
    values = {"start_year": sy, "end_year": ey}
    if not sy or not ey:
        return templates.TemplateResponse(
            request,
            "season_new.html",
            {"error": "Start year and end year are required.", "values": values},
            status_code=422,
        )
    try:
        sid = roster_repo.insert_season(sy, ey, _current_user_id(request))
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            request,
            "season_new.html",
            {
                "error": "A season with these years already exists.",
                "values": values,
            },
            status_code=422,
        )
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "season_new.html",
            {"error": "Could not save the season.", "values": values},
            status_code=500,
        )
    return RedirectResponse(url=f"/seasons/{sid}", status_code=303)


@router.get("/seasons/{season_id}", response_class=HTMLResponse, response_model=None)
async def season_detail(request: Request, season_id: int = Path(..., ge=1)):
    season = roster_repo.fetch_season(season_id)
    if season is None:
        return RedirectResponse(url="/seasons", status_code=303)
    enrollments = roster_repo.list_enrollments_for_season(season_id)
    return templates.TemplateResponse(
        request,
        "season_detail.html",
        {
            "season": season,
            "enrollments": enrollments,
            "error": None,
        },
    )


@router.get("/seasons/{season_id}/enroll", response_class=HTMLResponse, response_model=None)
async def enroll_form(request: Request, season_id: int = Path(..., ge=1)):
    season = roster_repo.fetch_season(season_id)
    if season is None:
        return RedirectResponse(url="/seasons", status_code=303)
    players = roster_repo.list_players_not_in_season(season_id)
    return templates.TemplateResponse(
        request,
        "enroll_new.html",
        {
            "season": season,
            "players": players,
            "error": None,
        },
    )


@router.post("/seasons/{season_id}/enroll", response_model=None)
async def enroll_submit(
    request: Request,
    season_id: int = Path(..., ge=1),
    player_id: int = Form(...),
):
    season = roster_repo.fetch_season(season_id)
    if season is None:
        return RedirectResponse(url="/seasons", status_code=303)
    eligible = {p["player_id"] for p in roster_repo.list_players_not_in_season(season_id)}
    if player_id not in eligible:
        return templates.TemplateResponse(
            request,
            "enroll_new.html",
            {
                "season": season,
                "players": roster_repo.list_players_not_in_season(season_id),
                "error": "That player is already enrolled or invalid.",
            },
            status_code=422,
        )
    try:
        ps_id = roster_repo.insert_player_season(
            player_id, season_id, _current_user_id(request)
        )
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            request,
            "enroll_new.html",
            {
                "season": season,
                "players": roster_repo.list_players_not_in_season(season_id),
                "error": "This player is already enrolled in this season.",
            },
            status_code=422,
        )
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "enroll_new.html",
            {
                "season": season,
                "players": roster_repo.list_players_not_in_season(season_id),
                "error": "Could not enroll the player.",
            },
            status_code=500,
        )
    return RedirectResponse(url=f"/player-season/{ps_id}", status_code=303)


@router.get("/player-season/{player_season_id}", response_class=HTMLResponse, response_model=None)
async def player_season_detail(
    request: Request,
    player_season_id: int = Path(..., ge=1),
):
    ps = roster_repo.fetch_player_season(player_season_id)
    if ps is None:
        return RedirectResponse(url="/seasons", status_code=303)
    stints = roster_repo.list_roster_stints(player_season_id)
    clubs = fetch_clubs()
    return templates.TemplateResponse(
        request,
        "player_season_detail.html",
        {
            "ps": ps,
            "stints": stints,
            "clubs": clubs,
            "error": None,
            "max_date": date.today().isoformat(),
        },
    )


@router.post("/player-season/{player_season_id}/stint", response_model=None)
async def roster_stint_create(
    request: Request,
    player_season_id: int = Path(..., ge=1),
    club_id: int = Form(...),
    start_date: str = Form(...),
    jersey_number: str = Form(""),
):
    ps = roster_repo.fetch_player_season(player_season_id)
    if ps is None:
        return RedirectResponse(url="/seasons", status_code=303)
    clubs = fetch_clubs()
    stints = roster_repo.list_roster_stints(player_season_id)
    ctx = {
        "ps": ps,
        "stints": stints,
        "clubs": clubs,
        "max_date": date.today().isoformat(),
    }
    try:
        roster_repo.parse_iso_date(start_date.strip())
    except ValueError:
        return templates.TemplateResponse(
            request,
            "player_season_detail.html",
            {**ctx, "error": "Start date must be YYYY-MM-DD."},
            status_code=422,
        )
    if not any(c["club_id"] == club_id for c in clubs):
        return templates.TemplateResponse(
            request,
            "player_season_detail.html",
            {**ctx, "error": "Invalid club."},
            status_code=422,
        )
    try:
        roster_repo.insert_roster_stint(
            player_season_id,
            club_id,
            start_date.strip(),
            jersey_number,
            _current_user_id(request),
        )
    except ValueError as e:
        return templates.TemplateResponse(
            request,
            "player_season_detail.html",
            {**ctx, "error": str(e)},
            status_code=422,
        )
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "player_season_detail.html",
            {**ctx, "error": "Could not save the roster stint."},
            status_code=500,
        )
    return RedirectResponse(url=f"/player-season/{player_season_id}", status_code=303)


@router.post("/roster-stint/{roster_stint_id}/end", response_model=None)
async def roster_stint_end(
    request: Request,
    roster_stint_id: int = Path(..., ge=1),
    end_date: str = Form(...),
):
    ps_id = roster_repo.fetch_roster_stint_player_season_id(roster_stint_id)
    if ps_id is None:
        return RedirectResponse(url="/seasons", status_code=303)
    try:
        roster_repo.parse_iso_date(end_date.strip())
    except ValueError:
        ps = roster_repo.fetch_player_season(ps_id)
        if ps is None:
            return RedirectResponse(url="/seasons", status_code=303)
        return templates.TemplateResponse(
            request,
            "player_season_detail.html",
            {
                "ps": ps,
                "stints": roster_repo.list_roster_stints(ps_id),
                "clubs": fetch_clubs(),
                "max_date": date.today().isoformat(),
                "error": "End date must be YYYY-MM-DD.",
            },
            status_code=422,
        )
    try:
        roster_repo.end_roster_stint(
            roster_stint_id,
            end_date.strip(),
            _current_user_id(request),
        )
    except ValueError as e:
        ps = roster_repo.fetch_player_season(ps_id)
        if ps is None:
            return RedirectResponse(url="/seasons", status_code=303)
        return templates.TemplateResponse(
            request,
            "player_season_detail.html",
            {
                "ps": ps,
                "stints": roster_repo.list_roster_stints(ps_id),
                "clubs": fetch_clubs(),
                "max_date": date.today().isoformat(),
                "error": str(e),
            },
            status_code=422,
        )
    return RedirectResponse(url=f"/player-season/{ps_id}", status_code=303)


@router.post("/roster-stint/{roster_stint_id}/enabled", response_model=None)
async def roster_stint_toggle_enabled(
    request: Request,
    roster_stint_id: int = Path(..., ge=1),
    enabled: str = Form(...),
):
    ps_id = roster_repo.fetch_roster_stint_player_season_id(roster_stint_id)
    if ps_id is None:
        return RedirectResponse(url="/seasons", status_code=303)
    try:
        roster_repo.set_roster_stint_enabled(
            roster_stint_id,
            enabled == "1",
            _current_user_id(request),
        )
    except sqlite3.Error:
        pass
    return RedirectResponse(url=f"/player-season/{ps_id}", status_code=303)
