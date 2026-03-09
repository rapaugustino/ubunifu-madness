from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Prediction, Team, EloRating, TourneySeed, TeamConference, TeamSeasonStats

router = APIRouter(tags=["predictions"])


def _team_base(team, elo, seed, conf, stats):
    record = f"{stats.wins}-{stats.losses}" if stats else None
    return {
        "id": team.id,
        "name": team.name,
        "gender": team.gender,
        "seed": seed,
        "conference": conf,
        "elo": round(elo, 1) if elo else None,
        "record": record,
        "winPct": round(stats.win_pct, 3) if stats else None,
    }


@router.get("/predictions/{team_a_id}/{team_b_id}")
def get_prediction(
    team_a_id: int,
    team_b_id: int,
    season: int = 2026,
    db: Session = Depends(get_db),
):
    # Normalize: lower ID first
    lo, hi = min(team_a_id, team_b_id), max(team_a_id, team_b_id)

    pred = (
        db.query(Prediction)
        .filter(
            Prediction.season == season,
            Prediction.team_a_id == lo,
            Prediction.team_b_id == hi,
        )
        .first()
    )
    if not pred:
        raise HTTPException(404, "Prediction not found for this matchup")

    # Load both teams
    team_lo = db.query(Team).get(lo)
    team_hi = db.query(Team).get(hi)

    def _get_extras(tid):
        elo = db.query(EloRating).filter(EloRating.season == season, EloRating.team_id == tid).first()
        seed = db.query(TourneySeed).filter(TourneySeed.season == season, TourneySeed.team_id == tid).first()
        conf = db.query(TeamConference).filter(TeamConference.season == season, TeamConference.team_id == tid).first()
        stats = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == season, TeamSeasonStats.team_id == tid).first()
        return (
            elo.elo if elo else None,
            seed.seed_number if seed else None,
            conf.conf_abbrev if conf else None,
            stats,
        )

    elo_lo, seed_lo, conf_lo, stats_lo = _get_extras(lo)
    elo_hi, seed_hi, conf_hi, stats_hi = _get_extras(hi)

    win_prob_a = pred.win_prob_a
    # If user passed team_a_id as the higher ID, flip probability
    if team_a_id > team_b_id:
        win_prob_a = 1 - pred.win_prob_a

    return {
        "season": season,
        "teamA": _team_base(
            team_lo if team_a_id <= team_b_id else team_hi,
            elo_lo if team_a_id <= team_b_id else elo_hi,
            seed_lo if team_a_id <= team_b_id else seed_hi,
            conf_lo if team_a_id <= team_b_id else conf_hi,
            stats_lo if team_a_id <= team_b_id else stats_hi,
        ),
        "teamB": _team_base(
            team_hi if team_a_id <= team_b_id else team_lo,
            elo_hi if team_a_id <= team_b_id else elo_lo,
            seed_hi if team_a_id <= team_b_id else seed_lo,
            conf_hi if team_a_id <= team_b_id else conf_lo,
            stats_hi if team_a_id <= team_b_id else stats_lo,
        ),
        "winProbA": round(win_prob_a, 4),
        "winProbB": round(1 - win_prob_a, 4),
        "modelVersion": pred.model_version,
    }
