from pydantic import BaseModel
from app.schemas.team import TeamBase


class MatchupResponse(BaseModel):
    teamA: TeamBase
    teamB: TeamBase
    winProbA: float
    round: int
    region: str
    slot: str | None = None


class BracketResponse(BaseModel):
    season: int
    gender: str
    matchups: list[MatchupResponse]


class SimulateRequest(BaseModel):
    season: int = 2026
    gender: str = "M"
    numSimulations: int = 1000
    lockedPicks: dict[str, int] | None = None


class ChampionProb(BaseModel):
    teamId: int
    teamName: str
    probability: float


class SimulateResponse(BaseModel):
    championProbabilities: list[ChampionProb]
    finalFourProbabilities: list[ChampionProb]
