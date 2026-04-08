"""HTTP Basic authentication for JSON API routes (curl / programmatic clients)."""

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_http_basic = HTTPBasic(auto_error=False)


def require_api_basic(
    credentials: HTTPBasicCredentials | None = Depends(_http_basic),
) -> None:
    expected_user = os.environ.get("BASKET_API_BASIC_USER", "").strip()
    expected_password = os.environ.get("BASKET_API_BASIC_PASSWORD", "").strip()

    if not expected_user or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API Basic auth is not configured. Set environment variables "
                "BASKET_API_BASIC_USER and BASKET_API_BASIC_PASSWORD before calling /api/*."
            ),
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, expected_user)
    pass_ok = secrets.compare_digest(credentials.password, expected_password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
