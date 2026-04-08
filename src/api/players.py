"""Players JSON API."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.auth import require_api_basic
from src.queries import load_players

router = APIRouter(
    tags=["players"],
    dependencies=[Depends(require_api_basic)],
)


class PlayerJSON(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: int
    name: str
    surname: str
    address: str | None
    date_of_birth: str


@router.get("/players", response_model=list[PlayerJSON])
def list_players_json() -> list[PlayerJSON]:
    try:
        rows = load_players()
    except sqlite3.Error:
        raise HTTPException(
            status_code=500,
            detail="Could not read players from the database.",
        )
    return [PlayerJSON.model_validate(r) for r in rows]
