"""
Shared team data helpers used across routers.

Consolidates the team dict construction and batch-loading patterns
that were previously duplicated in teams, predictions, compare, and bracket routers.
"""

from sqlalchemy.orm import Session

from app.models import (
    Team, EloRating, TourneySeed, TeamConference,
    TeamSeasonStats, ConferenceStrength, Conference,
)


def build_team_dict(
    team: Team,
    elo_val: float | None,
    seed_num: int | None,
    conf: str | None,
    stats: TeamSeasonStats | None,
) -> dict:
    """Build the standard team response dict from pre-loaded values."""
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


def build_team_dict_from_maps(
    team: Team,
    elo_map: dict,
    seed_map: dict,
    conf_map: dict,
    stats_map: dict,
) -> dict:
    """Build team dict using pre-loaded maps (avoids N+1 queries)."""
    return build_team_dict(
        team,
        elo_map.get(team.id),
        seed_map.get(team.id),
        conf_map.get(team.id),
        stats_map.get(team.id),
    )


def batch_load_team_data(
    db: Session,
    season: int,
    team_ids: list[int],
    stats_season: int | None = None,
) -> tuple[dict, dict, dict, dict]:
    """Pre-load elo, seed, conference, and stats data for a set of team IDs.

    Returns (elo_map, seed_map, conf_map, stats_map).

    stats_season: if provided, load stats/conf/elo from this season
    (useful when bracket is from an older season but we want current records).
    """
    data_season = stats_season or season

    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating)
        .filter(EloRating.season == data_season, EloRating.team_id.in_(team_ids))
        .all()
    }
    seed_map = {
        r.team_id: r.seed_number
        for r in db.query(TourneySeed)
        .filter(TourneySeed.season == season, TourneySeed.team_id.in_(team_ids))
        .all()
    }
    conf_names = {r.abbrev: r.description for r in db.query(Conference).all()}
    conf_map = {
        r.team_id: conf_names.get(r.conf_abbrev, r.conf_abbrev)
        for r in db.query(TeamConference)
        .filter(TeamConference.season == data_season, TeamConference.team_id.in_(team_ids))
        .all()
    }
    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats)
        .filter(TeamSeasonStats.season == data_season, TeamSeasonStats.team_id.in_(team_ids))
        .all()
    }
    # Fallback: if stats_map is empty and data_season != season, try the bracket season
    if not stats_map and data_season != season:
        stats_map = {
            r.team_id: r
            for r in db.query(TeamSeasonStats)
            .filter(TeamSeasonStats.season == season, TeamSeasonStats.team_id.in_(team_ids))
            .all()
        }
    return elo_map, seed_map, conf_map, stats_map


def build_stats_dict(stats: TeamSeasonStats) -> dict | None:
    """Build the stats sub-dict for team detail endpoints."""
    if not stats:
        return None
    return {
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


def build_conf_context(
    db: Session, team: Team, conf_row: TeamConference, season: int,
) -> dict | None:
    """Build the conference context sub-dict for team detail endpoints."""
    if not conf_row:
        return None
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
    if not cs:
        return None
    return {
        "confAbbrev": conf_row.conf_abbrev,
        "confName": conf_desc.description if conf_desc else conf_row.conf_abbrev,
        "avgElo": cs.avg_elo,
        "depth": cs.elo_depth,
        "top5Elo": cs.top5_elo,
        "ncWinrate": cs.nc_winrate,
        "tourneyHistWinrate": cs.tourney_hist_winrate,
    }
