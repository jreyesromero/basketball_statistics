"""Admin-only user management (requires is_admin; /admin/*)."""

import sqlite3

from fastapi import APIRouter, Form, Path, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.db_paths import SRC_DIR
from src.passwords import hash_password
from src.users_repo import (
    count_active_admins,
    delete_user,
    fetch_user_by_id,
    insert_user,
    list_all_users,
    set_user_active,
    set_user_admin,
    sole_active_admin_user_id,
)

templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))

router = APIRouter(prefix="/admin", tags=["admin"])


def _plausible_email(value: str) -> bool:
    s = value.strip()
    if not s or len(s) > 254 or " " in s or s.count("@") != 1:
        return False
    local, domain = s.split("@", 1)
    return bool(local) and bool(domain) and "." in domain


def _redirect_users(msg: str | None = None, err: str | None = None) -> RedirectResponse:
    q: list[str] = []
    if msg:
        q.append(f"msg={msg}")
    if err:
        q.append(f"err={err}")
    suffix = ("?" + "&".join(q)) if q else ""
    return RedirectResponse(url=f"/admin/users{suffix}", status_code=303)


@router.get("/users", response_class=HTMLResponse, response_model=None)
async def admin_users_list(
    request: Request,
    msg: str | None = Query(None),
    err: str | None = Query(None),
):
    users = list_all_users()
    sole_admin = sole_active_admin_user_id()
    current_id = request.state.current_user["user_id"]
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "users": users,
            "sole_active_admin_id": sole_admin,
            "current_user_id": current_id,
            "flash_msg": msg,
            "flash_err": err,
        },
    )


@router.get("/users/new", response_class=HTMLResponse, response_model=None)
async def admin_user_new_form(request: Request):
    return templates.TemplateResponse(
        request,
        "admin_user_new.html",
        {"error": None, "values": {}},
    )


@router.post("/users/new", response_model=None)
async def admin_user_new_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    is_active: str | None = Form(None),
    is_admin: str | None = Form(None),
):
    email_t = email.strip()
    values = {"email": email_t}
    active = is_active == "1"
    admin = is_admin == "1"

    if not _plausible_email(email_t):
        return templates.TemplateResponse(
            request,
            "admin_user_new.html",
            {"error": "Enter a valid email address.", "values": values},
            status_code=422,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "admin_user_new.html",
            {"error": "Password must be at least 8 characters.", "values": values},
            status_code=422,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "admin_user_new.html",
            {"error": "Passwords do not match.", "values": values},
            status_code=422,
        )
    try:
        insert_user(
            email_t,
            hash_password(password),
            is_active=active,
            is_admin=admin,
        )
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            request,
            "admin_user_new.html",
            {
                "error": "An account with this email already exists.",
                "values": values,
            },
            status_code=422,
        )
    except sqlite3.Error:
        return templates.TemplateResponse(
            request,
            "admin_user_new.html",
            {"error": "Could not create the user. Try again.", "values": values},
            status_code=500,
        )
    return _redirect_users(msg="created")


@router.post("/users/{user_id}/set-active", response_model=None)
async def admin_set_active(
    request: Request,
    user_id: int = Path(..., ge=1),
    active: str = Form(...),
):
    target = fetch_user_by_id(user_id)
    if target is None:
        return _redirect_users(err="user_not_found")
    want_active = active == "1"
    if not want_active and target["is_admin"] and target["is_active"]:
        if count_active_admins() == 1 and sole_active_admin_user_id() == user_id:
            return _redirect_users(err="cannot_deactivate_last_admin")
    try:
        set_user_active(user_id, active=want_active)
    except sqlite3.Error:
        return _redirect_users(err="db_error")
    return _redirect_users(msg="updated")


@router.post("/users/{user_id}/set-admin", response_model=None)
async def admin_set_admin(
    request: Request,
    user_id: int = Path(..., ge=1),
    admin: str = Form(...),
):
    target = fetch_user_by_id(user_id)
    if target is None:
        return _redirect_users(err="user_not_found")
    want_admin = admin == "1"
    if not want_admin and target["is_admin"]:
        if count_active_admins() == 1 and sole_active_admin_user_id() == user_id:
            return _redirect_users(err="cannot_demote_last_admin")
    try:
        set_user_admin(user_id, admin=want_admin)
    except sqlite3.Error:
        return _redirect_users(err="db_error")
    return _redirect_users(msg="updated")


@router.post("/users/{user_id}/delete", response_model=None)
async def admin_delete_user(
    request: Request,
    user_id: int = Path(..., ge=1),
):
    current_id = request.state.current_user["user_id"]
    if user_id == current_id:
        return _redirect_users(err="cannot_delete_self")
    target = fetch_user_by_id(user_id)
    if target is None:
        return _redirect_users(err="user_not_found")
    if target["is_admin"] and count_active_admins() == 1 and sole_active_admin_user_id() == user_id:
        return _redirect_users(err="cannot_delete_last_admin")
    try:
        delete_user(user_id)
    except sqlite3.Error:
        return _redirect_users(err="db_error")
    return _redirect_users(msg="deleted")
