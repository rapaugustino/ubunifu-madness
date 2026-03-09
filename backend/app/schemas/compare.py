from pydantic import BaseModel
from app.schemas.team import TeamDetail


class FeatureComparison(BaseModel):
    label: str
    teamA: float
    teamB: float
    unit: str
    lowerBetter: bool = False


class CompareResponse(BaseModel):
    teamA: TeamDetail
    teamB: TeamDetail
    winProbA: float
    winProbB: float
    featureComparison: list[FeatureComparison]
