from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Team, EloRating, TourneySeed, TeamConference,
    TeamSeasonStats, Prediction, ConferenceStrength, Conference,
)
from app.services.predictor import explain_matchup
from app.services.style_analysis import analyze_style_matchup

router = APIRouter(tags=["compare"])


def _load_team_detail(db: Session, team_id: int, season: int):
    team = db.query(Team).get(team_id)
    if not team:
        return None

    elo = db.query(EloRating).filter(EloRating.season == season, EloRating.team_id == team_id).first()
    seed = db.query(TourneySeed).filter(TourneySeed.season == season, TourneySeed.team_id == team_id).first()
    conf = db.query(TeamConference).filter(TeamConference.season == season, TeamConference.team_id == team_id).first()
    stats = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == season, TeamSeasonStats.team_id == team_id).first()

    record = f"{stats.wins}-{stats.losses}" if stats else None

    # Full conference name
    conf_name = None
    if conf:
        conf_desc = db.query(Conference).filter(Conference.abbrev == conf.conf_abbrev).first()
        conf_name = conf_desc.description if conf_desc else conf.conf_abbrev

    base = {
        "id": team.id,
        "name": team.name,
        "gender": team.gender,
        "seed": seed.seed_number if seed else None,
        "conference": conf_name,
        "elo": round(elo.elo, 1) if elo else None,
        "record": record,
        "winPct": round(stats.win_pct, 3) if stats else None,
        "logo": team.logo_url,
        "color": team.color,
    }

    stats_dict = None
    if stats:
        stats_dict = {
            "offEfficiency": stats.avg_off_eff,
            "defEfficiency": stats.avg_def_eff,
            "tempo": stats.avg_tempo,
            "efgPct": stats.avg_efg_pct,
            "toPct": stats.avg_to_pct,
            "orPct": stats.avg_or_pct,
            "ftRate": stats.avg_ft_rate,
            "oppEfgPct": stats.avg_opp_efg_pct,
            "oppToPct": stats.avg_opp_to_pct,
            "sos": stats.sos,
            "masseyRank": stats.massey_avg_rank,
            "momentum": {
                "lastNWinPct": stats.last_n_winpct,
                "lastNMov": stats.last_n_mov,
                "efgTrend": stats.efg_trend,
            },
            "coach": {
                "name": stats.coach_name,
                "tenure": stats.coach_tenure,
                "tourneyAppearances": stats.coach_tourney_appearances,
                "marchWinrate": stats.coach_march_winrate,
            },
        }

    conf_context = None
    if conf:
        cs = (
            db.query(ConferenceStrength)
            .filter(
                ConferenceStrength.season == season,
                ConferenceStrength.gender == team.gender,
                ConferenceStrength.conf_abbrev == conf.conf_abbrev,
            )
            .first()
        )
        conf_desc = db.query(Conference).filter(Conference.abbrev == conf.conf_abbrev).first()
        if cs:
            conf_context = {
                "confAbbrev": conf.conf_abbrev,
                "confName": conf_desc.description if conf_desc else conf.conf_abbrev,
                "avgElo": cs.avg_elo,
                "depth": cs.elo_depth,
                "top5Elo": cs.top5_elo,
                "ncWinrate": cs.nc_winrate,
                "tourneyHistWinrate": cs.tourney_hist_winrate,
            }

    return {**base, "stats": stats_dict, "conferenceContext": conf_context}


@router.get("/compare/{team_a_id}/{team_b_id}")
def compare_teams(
    team_a_id: int,
    team_b_id: int,
    season: int = 2026,
    db: Session = Depends(get_db),
):
    detail_a = _load_team_detail(db, team_a_id, season)
    detail_b = _load_team_detail(db, team_b_id, season)
    if not detail_a or not detail_b:
        raise HTTPException(404, "One or both teams not found")

    # Get prediction
    lo, hi = min(team_a_id, team_b_id), max(team_a_id, team_b_id)
    pred = (
        db.query(Prediction)
        .filter(Prediction.season == season, Prediction.team_a_id == lo, Prediction.team_b_id == hi)
        .first()
    )

    if pred:
        win_prob_a = pred.win_prob_a if team_a_id == lo else (1 - pred.win_prob_a)
    else:
        # Fallback: Elo-based probability
        elo_a = detail_a.get("elo") or 1500
        elo_b = detail_b.get("elo") or 1500
        win_prob_a = 1 / (1 + 10 ** ((elo_b - elo_a) / 400))

    # Build feature comparison from stats
    stats_a = detail_a.get("stats") or {}
    stats_b = detail_b.get("stats") or {}

    feature_comp = []
    # Fields on 0-100 scale that need converting to 0-1 for consistent frontend display
    pct_scale_100 = {"toPct", "oppToPct"}

    comparisons = [
        ("Offensive Efficiency", "offEfficiency", "pts/100", False),
        ("Defensive Efficiency", "defEfficiency", "pts/100", True),
        ("Tempo", "tempo", "poss/g", False),
        ("eFG%", "efgPct", "%", False),
        ("Turnover Rate", "toPct", "%", True),
        ("Rebound Rate", "orPct", "%", False),
        ("Free Throw Rate", "ftRate", "%", False),
        ("Opp eFG%", "oppEfgPct", "%", True),
        ("Strength of Schedule", "sos", "Elo", False),
    ]
    for label, key, unit, lower_better in comparisons:
        val_a = stats_a.get(key)
        val_b = stats_b.get(key)
        if val_a is not None and val_b is not None:
            # Normalize 0-100 scale fields to 0-1 so frontend can uniformly * 100
            if key in pct_scale_100:
                val_a = val_a / 100
                val_b = val_b / 100
            feature_comp.append({
                "label": label,
                "teamA": round(val_a, 4),
                "teamB": round(val_b, 4),
                "unit": unit,
                "lowerBetter": lower_better,
            })

    explanation = explain_matchup(db, team_a_id, team_b_id)
    style_analysis = analyze_style_matchup(db, team_a_id, team_b_id)

    return {
        "teamA": detail_a,
        "teamB": detail_b,
        "winProbA": round(win_prob_a, 4),
        "winProbB": round(1 - win_prob_a, 4),
        "featureComparison": feature_comp,
        "explanation": explanation,
        "styleAnalysis": style_analysis,
    }
