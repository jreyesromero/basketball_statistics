"""Seasons, season teams (clubs), and team rosters (HTML UI)."""

import sqlite3
from fastapi import APIRouter, Form, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.db_paths import SRC_DIR
from src import roster_repo

templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))

router = APIRouter(tags=["roster"])


def _current_user_id(request: Request) -> int:
    return int(request.state.current_user["user_id"])


def _season_team_detail_bundle(
    season_team_id: int,
    *,
    error: str | None,
) -> dict | None:
    """Context for team roster page; None if team missing."""
    team = roster_repo.fetch_season_team(season_team_id)
    if team is None:
        return None
    sid = int(team["season_id"])
    season = roster_repo.fetch_season(sid)
    if season is None:
        return None
    return {
        "team": team,
        "season": season,
        "players": roster_repo.list_players_on_team(season_team_id),
        "available_players": roster_repo.list_players_not_assigned_in_season(sid),
        "error": error,
    }


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
    teams = roster_repo.list_teams_for_season(season_id)
    return templates.TemplateResponse(
        request,
        "season_detail.html",
        {
            "season": season,
            "teams": teams,
            "error": None,
        },
    )


@router.get("/seasons/{season_id}/add-team", response_class=HTMLResponse, response_model=None)
async def add_team_form(request: Request, season_id: int = Path(..., ge=1)):
    season = roster_repo.fetch_season(season_id)
    if season is None:
        return RedirectResponse(url="/seasons", status_code=303)
    clubs = roster_repo.list_clubs_not_in_season(season_id)
    return templates.TemplateResponse(
        request,
        "season_add_team.html",
        {
            "season": season,
            "clubs": clubs,
            "error": None,
        },
    )


@router.post("/seasons/{season_id}/add-team", response_model=None)
async def add_team_submit(
    request: Request,
    season_id: int = Path(..., ge=1),
    club_id: int = Form(...),
):
    season = roster_repo.fetch_season(season_id)
    if season is None:
        return RedirectResponse(url="/seasons", status_code=303)
    eligible = {c["club_id"] for c in roster_repo.list_clubs_not_in_season(season_id)}
    if club_id not in eligible:
        return templates.TemplateResponse(
            request,
            "season_add_team.html",
            {
                "season": season,
                "clubs": roster_repo.list_clubs_not_in_season(season_id),
                "error": "That club is already in this season or is invalid.",
            },
            status_code=422,
        )
    try:
        roster_repo.insert_season_team(
            season_id, club_id, _current_user_id(request)
        )
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            request,
            "season_add_team.html",
            {
                "season": season,
                "clubs": roster_repo.list_clubs_not_in_season(season_id),
                "error": "This club is already registered for this season.",
            },
            status_code=422,
        )
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "season_add_team.html",
            {
                "season": season,
                "clubs": roster_repo.list_clubs_not_in_season(season_id),
                "error": "Could not add the team.",
            },
            status_code=500,
        )
    return RedirectResponse(url=f"/seasons/{season_id}", status_code=303)


@router.get("/seasons/{season_id}/team-management", response_model=None)
async def team_management_redirect(season_id: int = Path(..., ge=1)):
    """Old URL: send users back to the season page (rosters are per team now)."""
    season = roster_repo.fetch_season(season_id)
    if season is None:
        return RedirectResponse(url="/seasons", status_code=303)
    return RedirectResponse(url=f"/seasons/{season_id}", status_code=303)


@router.post("/season-team/{season_team_id}/remove", response_model=None)
async def remove_team_from_season(
    request: Request,
    season_team_id: int = Path(..., ge=1),
):
    st = roster_repo.fetch_season_team(season_team_id)
    if st is None:
        return RedirectResponse(url="/seasons", status_code=303)
    sid = int(st["season_id"])
    try:
        roster_repo.delete_season_team(season_team_id, _current_user_id(request))
    except ValueError:
        return RedirectResponse(url=f"/seasons/{sid}", status_code=303)
    except sqlite3.Error:
        pass
    return RedirectResponse(url=f"/seasons/{sid}", status_code=303)


@router.get("/season-team/{season_team_id}", response_class=HTMLResponse, response_model=None)
async def season_team_detail(
    request: Request,
    season_team_id: int = Path(..., ge=1),
):
    ctx = _season_team_detail_bundle(season_team_id, error=None)
    if ctx is None:
        return RedirectResponse(url="/seasons", status_code=303)
    return templates.TemplateResponse(
        request,
        "season_team_detail.html",
        ctx,
    )


@router.post("/season-team/{season_team_id}/assign-player", response_model=None)
async def assign_player_to_team(
    request: Request,
    season_team_id: int = Path(..., ge=1),
    player_id: int = Form(...),
    jersey_number: str = Form(""),
):
    st = roster_repo.fetch_season_team(season_team_id)
    if st is None:
        return RedirectResponse(url="/seasons", status_code=303)
    sid = int(st["season_id"])
    eligible = {
        p["player_id"] for p in roster_repo.list_players_not_assigned_in_season(sid)
    }

    def err_response(msg: str):
        ctx = _season_team_detail_bundle(season_team_id, error=msg)
        if ctx is None:
            return RedirectResponse(url="/seasons", status_code=303)
        return templates.TemplateResponse(
            request,
            "season_team_detail.html",
            ctx,
            status_code=422,
        )

    if player_id not in eligible:
        return err_response(
            "That player is already on a team this season or is invalid."
        )
    try:
        roster_repo.insert_team_player(
            season_team_id,
            player_id,
            jersey_number,
            _current_user_id(request),
        )
    except ValueError as e:
        return err_response(str(e))
    except sqlite3.IntegrityError:
        return err_response("This player is already assigned in this season.")
    except sqlite3.Error:
        return err_response("Could not assign the player.")
    return RedirectResponse(
        url=f"/season-team/{season_team_id}",
        status_code=303,
    )


@router.post("/season-team-player/{season_team_player_id}/remove", response_model=None)
async def remove_player_from_team(
    request: Request,
    season_team_player_id: int = Path(..., ge=1),
):
    st_id = roster_repo.fetch_season_team_id_for_team_player_row(
        season_team_player_id
    )
    if st_id is None:
        return RedirectResponse(url="/seasons", status_code=303)
    try:
        roster_repo.delete_team_player(
            season_team_player_id,
            _current_user_id(request),
        )
    except ValueError:
        return RedirectResponse(url=f"/season-team/{st_id}", status_code=303)
    except sqlite3.Error:
        pass
    return RedirectResponse(
        url=f"/season-team/{st_id}",
        status_code=303,
    )
