from pydantic import BaseModel


class StatusOut(BaseModel):
    ready: bool
    error: str | None = None
    n_interventions: int = 0
    n_games: int = 0
    n_players: int = 0
    exposure_verified: bool = False
    season: int | None = None
