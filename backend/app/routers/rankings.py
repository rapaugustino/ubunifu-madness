from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import (
    Team, EloRating, TeamSeasonStats, TeamConference,
    TourneySeed, ConferenceStrength, Conference, ConferenceStanding,
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
    # Get all teams with Elo for this season+gender, ordered by power rating desc (Elo as fallback)
    rows = (
        db.query(Team, EloRating, TeamSeasonStats)
        .join(EloRating, EloRating.team_id == Team.id)
        .outerjoin(TeamSeasonStats, (TeamSeasonStats.team_id == Team.id) & (TeamSeasonStats.season == season))
        .filter(EloRating.season == season, Team.gender == gender)
        .order_by(
            TeamSeasonStats.power_rating.desc().nullslast(),
            EloRating.elo.desc(),
        )
        .all()
    )

    total = len(rows)
    rows = rows[offset : offset + limit]

    team_ids = [t.id for t, _, _ in rows]

    # Stats already loaded via join
    stats_map = {s.team_id: s for _, _, s in rows if s}
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
    for i, (team, elo_row, _stats_row) in enumerate(rows):
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
            # Advanced metrics
            "adjOE": stats.adj_off_eff if stats else None,
            "adjDE": stats.adj_def_eff if stats else None,
            "adjEM": stats.adj_net_eff if stats else None,
            "barthag": stats.barthag if stats else None,
            "luck": stats.luck if stats else None,
            "trueShooting": stats.true_shooting_pct if stats else None,
            "oppTrueShooting": stats.opp_true_shooting_pct if stats else None,
            "threePtRate": stats.three_pt_rate if stats else None,
            "astToRatio": stats.ast_to_ratio if stats else None,
            "drbPct": stats.drb_pct if stats else None,
            "stlPct": stats.stl_pct if stats else None,
            "blkPct": stats.blk_pct if stats else None,
            "marginStdev": stats.margin_stdev if stats else None,
            "floorEff": stats.floor_eff if stats else None,
            "ceilingEff": stats.ceiling_eff if stats else None,
            "upsetVulnerability": stats.upset_vulnerability if stats else None,
            "closeRecord": f"{stats.close_wins}-{stats.close_losses}" if stats and stats.close_wins is not None else None,
            "closeWinPct": stats.close_game_win_pct if stats else None,
            "pythWinPct": stats.pyth_win_pct if stats else None,
            "tempo": stats.avg_tempo if stats else None,
            "sos": stats.sos if stats else None,
            "powerRating": round(stats.power_rating, 1) if stats and stats.power_rating else None,
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

    # Aggregate advanced stats per conference from TeamSeasonStats
    conf_adv_raw = (
        db.query(
            TeamConference.conf_abbrev,
            func.avg(TeamSeasonStats.adj_net_eff),
            func.avg(TeamSeasonStats.avg_tempo),
            func.avg(TeamSeasonStats.true_shooting_pct),
            func.avg(TeamSeasonStats.upset_vulnerability),
            func.avg(TeamSeasonStats.barthag),
        )
        .join(Team, Team.id == TeamConference.team_id)
        .join(TeamSeasonStats, (TeamSeasonStats.team_id == Team.id) & (TeamSeasonStats.season == season))
        .filter(TeamConference.season == season, Team.gender == gender)
        .group_by(TeamConference.conf_abbrev)
        .all()
    )
    conf_adv = {
        row[0]: {"adjEM": row[1], "tempo": row[2], "tsPct": row[3], "upsetVuln": row[4], "barthag": row[5]}
        for row in conf_adv_raw
    }

    conferences = []
    for i, cs in enumerate(rows):
        adv = conf_adv.get(cs.conf_abbrev, {})
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
            "avgAdjEM": round(adv.get("adjEM") or 0, 1),
            "avgTempo": round(adv.get("tempo") or 0, 1),
            "avgTsPct": round((adv.get("tsPct") or 0) * 100, 1),
            "avgUpsetVuln": round(adv.get("upsetVuln") or 0, 1),
            "avgBarthag": round(adv.get("barthag") or 0, 3),
        })

    return {"conferences": conferences}


@router.get("/rankings/conference-standings")
def conference_standings(
    gender: str = Query("M", pattern="^(M|W)$"),
    conf: str | None = Query(None, description="Filter by conference abbreviation"),
    season: int = 2026,
    db: Session = Depends(get_db),
):
    """Get within-conference standings (team rankings within each conference)."""
    query = (
        db.query(ConferenceStanding, Team)
        .join(Team, Team.id == ConferenceStanding.team_id)
        .filter(
            ConferenceStanding.season == season,
            ConferenceStanding.gender == gender,
        )
    )
    if conf:
        query = query.filter(ConferenceStanding.conf_abbrev == conf)

    query = query.order_by(
        ConferenceStanding.conf_abbrev,
        ConferenceStanding.conf_seed,
    )
    rows = query.all()

    # Conference names
    conf_names = {r.abbrev: r.description for r in db.query(Conference).all()}

    # Elo lookup
    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating).filter(EloRating.season == season).all()
    }

    # Group by conference
    from collections import defaultdict
    grouped: dict[str, list] = defaultdict(list)
    for standing, team in rows:
        grouped[standing.conf_abbrev].append({
            "seed": standing.conf_seed,
            "team": {
                "id": team.id,
                "name": team.name,
                "logo": team.logo_url,
                "color": team.color,
                "elo": round(elo_map.get(team.id, 0), 1),
            },
            "confRecord": f"{standing.conf_wins}-{standing.conf_losses}",
            "confWinPct": round(standing.conf_win_pct or 0, 3),
            "overallRecord": f"{standing.overall_wins}-{standing.overall_losses}",
            "overallWinPct": round(standing.overall_win_pct or 0, 3),
            "homeRecord": f"{standing.home_wins}-{standing.home_losses}",
            "awayRecord": f"{standing.away_wins}-{standing.away_losses}",
            "streak": standing.streak or "",
            "gamesBehind": standing.games_behind or 0,
            "avgPointsFor": round(standing.avg_points_for or 0, 1),
            "avgPointsAgainst": round(standing.avg_points_against or 0, 1),
            "pointDiff": standing.point_differential or 0,
        })

    conferences = []
    for abbrev, teams in sorted(grouped.items(), key=lambda x: conf_names.get(x[0], x[0])):
        conferences.append({
            "abbrev": abbrev,
            "name": conf_names.get(abbrev, abbrev),
            "teams": teams,
        })

    return {"conferences": conferences}
