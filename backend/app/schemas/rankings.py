from pydantic import BaseModel
from app.schemas.team import TeamBase


class PowerRankingEntry(BaseModel):
    rank: int
    team: TeamBase
    elo: float
    record: str
    conference: str
    confStrength: float
    trend: str  # "up", "down", "same"
    trendAmount: float


class PowerRankingsResponse(BaseModel):
    rankings: list[PowerRankingEntry]
    total: int


class ConferenceRankingEntry(BaseModel):
    rank: int
    name: str
    abbrev: str
    avgElo: float
    depth: float
    ncWinRate: float
    teams: int
    tourneyBids: int
    top5Elo: float


class ConferenceRankingsResponse(BaseModel):
    conferences: list[ConferenceRankingEntry]
