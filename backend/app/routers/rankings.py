from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import (
    Team, EloRating, TeamSeasonStats, TeamConference,
    TourneySeed, ConferenceStrength, Conference,
)

router = APIRouter(tags=["rankings"])


@router.get("/rankings/power")
def power_rankings(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = 2026,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    # Get all teams with Elo for this season+gender, ordered by Elo desc
    rows = (
        db.query(Team, EloRating)
        .join(EloRating, EloRating.team_id == Team.id)
        .filter(EloRating.season == season, Team.gender == gender)
        .order_by(EloRating.elo.desc())
        .all()
    )

    total = len(rows)
    rows = rows[offset : offset + limit]

    team_ids = [t.id for t, _ in rows]

    # Batch load
    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats)
        .filter(TeamSeasonStats.season == season, TeamSeasonStats.team_id.in_(team_ids))
        .all()
    }
    conf_map = {
        r.team_id: r.conf_abbrev
        for r in db.query(TeamConference)
        .filter(TeamConference.season == season, TeamConference.team_id.in_(team_ids))
        .all()
    }
    seed_map = {
        r.team_id: r.seed_number
        for r in db.query(TourneySeed)
        .filter(TourneySeed.season == season, TourneySeed.team_id.in_(team_ids))
        .all()
    }

    # Conference strength lookup for nc_winrate (used as confStrength)
    cs_map = {}
    for r in (
        db.query(ConferenceStrength)
        .filter(ConferenceStrength.season == season, ConferenceStrength.gender == gender)
        .all()
    ):
        cs_map[r.conf_abbrev] = r.nc_winrate or 0

    # Conference full names
    conf_names = {r.abbrev: r.description for r in db.query(Conference).all()}

    rankings = []
    for i, (team, elo_row) in enumerate(rows):
        stats = stats_map.get(team.id)
        conf_abbrev = conf_map.get(team.id, "")
        conf_name = conf_names.get(conf_abbrev, conf_abbrev)
        record = f"{stats.wins}-{stats.losses}" if stats else "0-0"
        win_pct = stats.win_pct if stats else 0

        # Trend from momentum data
        trend = "same"
        trend_amount = 0
        if stats and stats.last_n_winpct is not None:
            if stats.last_n_winpct > win_pct + 0.05:
                trend = "up"
                trend_amount = round((stats.last_n_winpct - win_pct) * 100, 1)
            elif stats.last_n_winpct < win_pct - 0.05:
                trend = "down"
                trend_amount = round((win_pct - stats.last_n_winpct) * 100, 1)

        rankings.append({
            "rank": offset + i + 1,
            "team": {
                "id": team.id,
                "name": team.name,
                "gender": team.gender,
                "seed": seed_map.get(team.id),
                "conference": conf_name,
                "elo": round(elo_row.elo, 1),
                "record": record,
                "winPct": round(win_pct, 3),
                "logo": team.logo_url,
                "color": team.color,
            },
            "elo": round(elo_row.elo, 1),
            "record": record,
            "conference": conf_name,
            "confStrength": round(cs_map.get(conf_abbrev, 0), 3),
            "trend": trend,
            "trendAmount": trend_amount,
        })

    return {"rankings": rankings, "total": total}


@router.get("/rankings/conferences")
def conference_rankings(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = 2026,
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ConferenceStrength)
        .filter(ConferenceStrength.season == season, ConferenceStrength.gender == gender)
        .order_by(ConferenceStrength.avg_elo.desc())
        .all()
    )

    # Count teams per conference
    team_counts = dict(
        db.query(TeamConference.conf_abbrev, func.count(TeamConference.team_id))
        .filter(TeamConference.season == season)
        .join(Team, Team.id == TeamConference.team_id)
        .filter(Team.gender == gender)
        .group_by(TeamConference.conf_abbrev)
        .all()
    )

    # Count tourney bids per conference
    bid_counts = dict(
        db.query(TeamConference.conf_abbrev, func.count(TourneySeed.team_id))
        .join(TourneySeed, (TourneySeed.team_id == TeamConference.team_id) & (TourneySeed.season == TeamConference.season))
        .join(Team, Team.id == TeamConference.team_id)
        .filter(TeamConference.season == season, Team.gender == gender)
        .group_by(TeamConference.conf_abbrev)
        .all()
    )

    # Conference names
    conf_names = {
        r.abbrev: r.description
        for r in db.query(Conference).all()
    }

    conferences = []
    for i, cs in enumerate(rows):
        conferences.append({
            "rank": i + 1,
            "name": conf_names.get(cs.conf_abbrev, cs.conf_abbrev),
            "abbrev": cs.conf_abbrev,
            "avgElo": round(cs.avg_elo, 1) if cs.avg_elo else 0,
            "depth": round(cs.elo_depth, 2) if cs.elo_depth else 0,
            "ncWinRate": round(cs.nc_winrate, 3) if cs.nc_winrate else 0,
            "teams": team_counts.get(cs.conf_abbrev, 0),
            "tourneyBids": bid_counts.get(cs.conf_abbrev, 0),
            "top5Elo": round(cs.top5_elo, 1) if cs.top5_elo else 0,
        })

    return {"conferences": conferences}
