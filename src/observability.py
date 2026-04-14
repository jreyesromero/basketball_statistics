"""Structured JSON logs, request correlation, and timing (stdout; optional rotating file).

Environment:
  BASKET_LOG_FILE — If set to a non-empty path, JSON lines are also appended there
    (RotatingFileHandler). Relative paths are resolved from the project root.
  BASKET_LOG_MAX_BYTES — Max size per file before rotation (default 5242880 = 5 MiB).
  BASKET_LOG_BACKUP_COUNT — Number of rotated files to keep (default 5).
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.db_paths import ROOT_DIR

_LOGGER = logging.getLogger("basket.observability")
_CONFIGURED = False


def configure_logging() -> None:
    """Stdout JSON lines; optional rotating file when BASKET_LOG_FILE is set (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    _LOGGER.setLevel(logging.INFO)
    _LOGGER.handlers.clear()
    _LOGGER.propagate = False
    fmt = logging.Formatter("%(message)s")
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(fmt)
    _LOGGER.addHandler(h)

    log_file = os.environ.get("BASKET_LOG_FILE", "").strip()
    if log_file:
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_path = ROOT_DIR / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.environ.get("BASKET_LOG_MAX_BYTES", "5242880"))
        backups = int(os.environ.get("BASKET_LOG_BACKUP_COUNT", "5"))
        fh = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=max(1024, max_bytes),
            backupCount=max(1, backups),
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        _LOGGER.addHandler(fh)


def log_json(event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Emit one JSON object per line (no secrets; keep values small)."""
    configure_logging()
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event": event,
    }
    for k, v in fields.items():
        if v is not None:
            payload[k] = v
    _LOGGER.log(level, json.dumps(payload, default=str, ensure_ascii=False))


def _path_template(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        p = getattr(route, "path", None)
        if isinstance(p, str) and p:
            return p
    return request.url.path


def _user_fields(request: Request) -> tuple[int | None, bool | None]:
    user = getattr(request.state, "current_user", None)
    if not isinstance(user, dict):
        return None, None
    uid = user.get("user_id")
    admin = user.get("is_admin")
    uid_i = int(uid) if uid is not None else None
    admin_b = bool(admin) if admin is not None else None
    return uid_i, admin_b


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Outermost middleware (add last): request_id, duration, route template, status, user_id.
    Adds X-Request-ID on responses.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            uid, admin = _user_fields(request)
            log_json(
                "http_request_failed",
                level=logging.ERROR,
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                path_template=_path_template(request),
                duration_ms=round(elapsed_ms, 2),
                user_id=uid,
                is_admin=admin,
                error_type=type(e).__name__,
            )
            _LOGGER.exception("Unhandled exception during request")
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        uid, admin = _user_fields(request)
        log_json(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            path_template=_path_template(request),
            status_code=response.status_code,
            duration_ms=round(elapsed_ms, 2),
            user_id=uid,
            is_admin=admin,
        )
        response.headers["X-Request-ID"] = request_id
        return response
