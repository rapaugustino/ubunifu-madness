from pydantic import BaseModel
from app.schemas.team import TeamBase


class PredictionResponse(BaseModel):
    season: int
    teamA: TeamBase
    teamB: TeamBase
    winProbA: float
    winProbB: float
    modelVersion: str
