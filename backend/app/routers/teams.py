from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, TeamConference, TourneySeed, EloRating, TeamSeasonStats, ConferenceStrength, Conference
from app.schemas.team import TeamBase, TeamDetail, TeamListResponse

router = APIRouter(tags=["teams"])


def _build_team_base(
    team: Team,
    elo_val: float | None,
    seed_num: int | None,
    conf: str | None,
    stats: TeamSeasonStats | None,
) -> dict:
    record = None
    win_pct = None
    if stats:
        record = f"{stats.wins}-{stats.losses}"
        win_pct = stats.win_pct
    return {
        "id": team.id,
        "name": team.name,
        "gender": team.gender,
        "seed": seed_num,
        "conference": conf,
        "elo": round(elo_val, 1) if elo_val else None,
        "record": record,
        "winPct": round(win_pct, 3) if win_pct else None,
        "logo": team.logo_url,
        "color": team.color,
    }


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
            _build_team_base(
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

    base = _build_team_base(
        team,
        elo_row.elo if elo_row else None,
        seed_row.seed_number if seed_row else None,
        conf_name,
        stats_row,
    )

    stats_dict = None
    if stats_row:
        stats_dict = {
            "offEfficiency": stats_row.avg_off_eff,
            "defEfficiency": stats_row.avg_def_eff,
            "tempo": stats_row.avg_tempo,
            "efgPct": stats_row.avg_efg_pct,
            "toPct": stats_row.avg_to_pct,
            "orPct": stats_row.avg_or_pct,
            "ftRate": stats_row.avg_ft_rate,
            "oppEfgPct": stats_row.avg_opp_efg_pct,
            "oppToPct": stats_row.avg_opp_to_pct,
            "masseyRank": stats_row.massey_avg_rank,
            "momentum": {
                "lastNWinPct": stats_row.last_n_winpct,
                "lastNMov": stats_row.last_n_mov,
                "efgTrend": stats_row.efg_trend,
            },
            "coach": {
                "name": stats_row.coach_name,
                "tenure": stats_row.coach_tenure,
                "tourneyAppearances": stats_row.coach_tourney_appearances,
                "marchWinrate": stats_row.coach_march_winrate,
            },
        }

    conf_context = None
    if conf_row:
        cs = (
            db.query(ConferenceStrength)
            .filter(
                ConferenceStrength.season == season,
                ConferenceStrength.gender == team.gender,
                ConferenceStrength.conf_abbrev == conf_row.conf_abbrev,
            )
            .first()
        )
        conf_desc = (
            db.query(Conference)
            .filter(Conference.abbrev == conf_row.conf_abbrev)
            .first()
        )
        if cs:
            conf_context = {
                "confAbbrev": conf_row.conf_abbrev,
                "confName": conf_desc.description if conf_desc else conf_row.conf_abbrev,
                "avgElo": cs.avg_elo,
                "depth": cs.elo_depth,
                "top5Elo": cs.top5_elo,
                "ncWinrate": cs.nc_winrate,
                "tourneyHistWinrate": cs.tourney_hist_winrate,
            }

    return {**base, "stats": stats_dict, "conferenceContext": conf_context}
