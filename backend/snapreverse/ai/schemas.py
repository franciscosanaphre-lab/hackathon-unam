from pydantic import BaseModel, Field


class AnalyzeIn(BaseModel):
    nflId: int
    gameId: int
    mode: str = Field("live", pattern="^(live|retro)$")
    refresh: bool = False


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=1500)


class ChatIn(BaseModel):
    nflId: int
    gameId: int
    mode: str = Field("live", pattern="^(live|retro)$")
    message: str = Field(min_length=1, max_length=800)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)
    playId: int | None = None
    refPlayId: int | None = None


class CompareIn(BaseModel):
    nflId: int
    gameId: int
    playId: int
    refGameId: int | None = None
    refPlayId: int
    mode: str = Field("live", pattern="^(live|retro)$")
