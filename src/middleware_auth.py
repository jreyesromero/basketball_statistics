"""Require a logged-in, active user for browser pages (not /api/* or /static/*)."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from src.users_repo import fetch_user_by_id


def _is_public_browser_path(path: str) -> bool:
    if path.startswith("/static/"):
        return True
    if path.startswith("/api/"):
        return True
    if path in ("/docs", "/openapi.json", "/redoc", "/favicon.ico"):
        return True
    p = path.rstrip("/") or "/"
    if p in ("/login", "/register"):
        return True
    return False


class RequireLoginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.current_user = None
        path = request.url.path
        if _is_public_browser_path(path):
            return await call_next(request)

        uid = request.session.get("user_id")
        if uid is None:
            return RedirectResponse(url="/login", status_code=303)
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            request.session.clear()
            return RedirectResponse(url="/login", status_code=303)

        user = fetch_user_by_id(uid_int)
        if user is None or not user["is_active"]:
            request.session.clear()
            return RedirectResponse(url="/login", status_code=303)

        request.state.current_user = {
            "user_id": user["user_id"],
            "email": user["email"],
        }
        return await call_next(request)
