from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, TeamConference, TourneySeed, EloRating, TeamSeasonStats, ConferenceStrength, Conference
from app.schemas.team import TeamDetail, TeamListResponse
from app.utils.team_helpers import build_team_dict, build_stats_dict, build_conf_context

router = APIRouter(tags=["teams"])


@router.get("/teams", response_model=TeamListResponse)
def list_teams(
    gender: str = Query("all", pattern="^(M|W|all)$"),
    season: int = 2026,
    search: str = "",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Team)
    if gender != "all":
        q = q.filter(Team.gender == gender)
    if search:
        q = q.filter(Team.name.ilike(f"%{search}%"))

    # Only include teams active in this season
    active_ids = (
        db.query(TeamConference.team_id)
        .filter(TeamConference.season == season)
        .subquery()
    )
    q = q.filter(Team.id.in_(db.query(active_ids.c.team_id)))

    total = q.count()
    teams_db = q.order_by(Team.name).offset(offset).limit(limit).all()

    # Batch load related data
    team_ids = [t.id for t in teams_db]

    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating)
        .filter(EloRating.season == season, EloRating.team_id.in_(team_ids))
        .all()
    }
    seed_map = {
        r.team_id: r.seed_number
        for r in db.query(TourneySeed)
        .filter(TourneySeed.season == season, TourneySeed.team_id.in_(team_ids))
        .all()
    }
    # Conference abbrev -> full name
    conf_names = {r.abbrev: r.description for r in db.query(Conference).all()}
    conf_map = {
        r.team_id: conf_names.get(r.conf_abbrev, r.conf_abbrev)
        for r in db.query(TeamConference)
        .filter(TeamConference.season == season, TeamConference.team_id.in_(team_ids))
        .all()
    }
    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats)
        .filter(
            TeamSeasonStats.season == season, TeamSeasonStats.team_id.in_(team_ids)
        )
        .all()
    }

    result = []
    for t in teams_db:
        result.append(
            build_team_dict(
                t,
                elo_map.get(t.id),
                seed_map.get(t.id),
                conf_map.get(t.id),
                stats_map.get(t.id),
            )
        )

    return {"teams": result, "total": total}


@router.get("/teams/{team_id}", response_model=TeamDetail)
def get_team(team_id: int, season: int = 2026, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    elo_row = (
        db.query(EloRating)
        .filter(EloRating.season == season, EloRating.team_id == team_id)
        .first()
    )
    seed_row = (
        db.query(TourneySeed)
        .filter(TourneySeed.season == season, TourneySeed.team_id == team_id)
        .first()
    )
    conf_row = (
        db.query(TeamConference)
        .filter(TeamConference.season == season, TeamConference.team_id == team_id)
        .first()
    )
    stats_row = (
        db.query(TeamSeasonStats)
        .filter(
            TeamSeasonStats.season == season, TeamSeasonStats.team_id == team_id
        )
        .first()
    )

    # Full conference name
    conf_name = None
    if conf_row:
        conf_desc = db.query(Conference).filter(Conference.abbrev == conf_row.conf_abbrev).first()
        conf_name = conf_desc.description if conf_desc else conf_row.conf_abbrev

    base = build_team_dict(
        team,
        elo_row.elo if elo_row else None,
        seed_row.seed_number if seed_row else None,
        conf_name,
        stats_row,
    )

    stats_dict = build_stats_dict(stats_row)
    conf_context = build_conf_context(db, team, conf_row, season)

    return {**base, "stats": stats_dict, "conferenceContext": conf_context}
