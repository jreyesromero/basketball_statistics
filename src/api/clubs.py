"""Clubs JSON API."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.auth import require_api_basic
from src.queries import load_clubs

router = APIRouter(
    tags=["clubs"],
    dependencies=[Depends(require_api_basic)],
)


class ClubJSON(BaseModel):
    model_config = ConfigDict(extra="forbid")

    club_id: int
    name: str
    address: str | None
    foundation_date: str


@router.get("/clubs", response_model=list[ClubJSON])
def list_clubs_json() -> list[ClubJSON]:
    try:
        rows = load_clubs()
    except sqlite3.Error:
        raise HTTPException(
            status_code=500,
            detail="Could not read clubs from the database.",
        )
    return [ClubJSON.model_validate(r) for r in rows]
