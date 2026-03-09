from pydantic import BaseModel


class TeamBase(BaseModel):
    id: int
    name: str
    gender: str
    seed: int | None = None
    conference: str | None = None
    elo: float | None = None
    record: str | None = None
    winPct: float | None = None
    logo: str | None = None
    color: str | None = None


class TeamDetail(TeamBase):
    stats: dict | None = None
    conferenceContext: dict | None = None


class TeamListResponse(BaseModel):
    teams: list[TeamBase]
    total: int
