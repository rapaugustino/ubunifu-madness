"""Player data endpoints — roster, stats, importance, injuries."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, Player, PlayerSeasonStats
from app.services.player_sync import (
    sync_team_roster, sync_all_rosters,
    ingest_date_box_scores, recompute_season_stats,
    compute_importance_scores,
)

router = APIRouter(tags=["players"])

SEASON = 2026

# Leaderboard category → (sort column or expression, display label)
_LEADERBOARD_CATEGORIES = {
    "ppg", "rpg", "apg", "mpg",
    "fg_pct", "fg3_pct", "ft_pct",
    "spg", "bpg",
    "importance_score",
}


@router.get("/players/leaderboard")
def player_leaderboard(
    gender: str = Query("M", pattern="^(M|W)$"),
    category: str = Query("ppg"),
    min_games: int = Query(10, ge=1),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Top performers by statistical category for the season."""
    if category not in _LEADERBOARD_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Choose from: {sorted(_LEADERBOARD_CATEGORIES)}")

    # Computed per-game columns for steals and blocks
    gp = PlayerSeasonStats.games_played
    safe_gp = case((gp > 0, gp), else_=1)
    spg_expr = PlayerSeasonStats.stl_total / safe_gp
    bpg_expr = PlayerSeasonStats.blk_total / safe_gp

    sort_map = {
        "ppg": PlayerSeasonStats.ppg,
        "rpg": PlayerSeasonStats.rpg,
        "apg": PlayerSeasonStats.apg,
        "mpg": PlayerSeasonStats.mpg,
        "fg_pct": PlayerSeasonStats.fg_pct,
        "fg3_pct": PlayerSeasonStats.fg3_pct,
        "ft_pct": PlayerSeasonStats.ft_pct,
        "spg": spg_expr,
        "bpg": bpg_expr,
        "importance_score": PlayerSeasonStats.importance_score,
    }
    sort_col = sort_map[category]

    # Minimum attempt thresholds for percentage categories to avoid
    # misleading leaders (e.g. 100% FG on 2 total attempts).
    # ~3 attempts per game is standard for FG/3PT, ~2 for FT.
    pct_attempt_filters = {
        "fg_pct": PlayerSeasonStats.fga >= min_games * 3,
        "fg3_pct": PlayerSeasonStats.fga3 >= min_games * 2,
        "ft_pct": PlayerSeasonStats.fta >= min_games * 2,
    }

    base_q = (
        db.query(PlayerSeasonStats, Player, Team)
        .join(Player, PlayerSeasonStats.player_id == Player.id)
        .join(Team, Player.team_id == Team.id)
        .filter(
            Player.gender == gender,
            PlayerSeasonStats.season == SEASON,
            PlayerSeasonStats.games_played >= min_games,
            sort_col.isnot(None) if hasattr(sort_col, "isnot") else True,
        )
    )

    # Apply attempt threshold for percentage categories
    if category in pct_attempt_filters:
        base_q = base_q.filter(pct_attempt_filters[category])

    total = base_q.count()

    rows = (
        base_q
        .order_by(sort_col.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    players = []
    for i, (stats, player, team) in enumerate(rows):
        gp_val = stats.games_played or 1
        players.append({
            "rank": offset + i + 1,
            "playerId": player.id,
            "name": player.name,
            "position": player.position,
            "headshot": player.headshot_url,
            "teamId": team.id,
            "teamName": team.name,
            "teamLogo": team.logo_url,
            "teamColor": team.color,
            "gamesPlayed": stats.games_played,
            "statValue": round(
                (stats.stl_total / gp_val) if category == "spg"
                else (stats.blk_total / gp_val) if category == "bpg"
                else getattr(stats, category) or 0,
                1 if category in ("ppg", "rpg", "apg", "mpg") else 3,
            ),
            "stats": {
                "ppg": stats.ppg,
                "rpg": stats.rpg,
                "apg": stats.apg,
                "mpg": stats.mpg,
                "fgPct": stats.fg_pct,
                "fg3Pct": stats.fg3_pct,
                "ftPct": stats.ft_pct,
                "spg": round((stats.stl_total or 0) / gp_val, 1),
                "bpg": round((stats.blk_total or 0) / gp_val, 1),
                "importanceScore": stats.importance_score,
            },
        })

    return {"players": players, "total": total, "category": category, "gender": gender}


@router.get("/players/{team_id}")
def team_players(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Get roster with season stats and importance scores for a team."""
    team = db.query(Team).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")

    players = (
        db.query(Player)
        .filter(Player.team_id == team_id)
        .order_by(Player.name)
        .all()
    )

    result = []
    for p in players:
        stats = (
            db.query(PlayerSeasonStats)
            .filter(PlayerSeasonStats.season == SEASON, PlayerSeasonStats.player_id == p.id)
            .first()
        )
        result.append({
            "id": p.id,
            "espnId": p.espn_id,
            "name": p.name,
            "jersey": p.jersey,
            "position": p.position,
            "positionFull": p.position_full,
            "height": p.height,
            "weight": p.weight,
            "experience": p.experience,
            "headshot": p.headshot_url,
            "injuryStatus": p.injury_status,
            "injuryDetail": p.injury_detail,
            "stats": {
                "gamesPlayed": stats.games_played,
                "ppg": stats.ppg,
                "rpg": stats.rpg,
                "apg": stats.apg,
                "mpg": stats.mpg,
                "fgPct": stats.fg_pct,
                "fg3Pct": stats.fg3_pct,
                "ftPct": stats.ft_pct,
                "importanceScore": stats.importance_score,
                "minutesShare": stats.minutes_share,
            } if stats else None,
        })

    return {
        "teamId": team_id,
        "teamName": team.name,
        "players": result,
    }


@router.post("/players/sync-rosters")
def sync_rosters(
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """Sync all team rosters from ESPN."""
    result = sync_all_rosters(db, gender)
    return {"status": "ok", "gender": gender, **result}


@router.post("/players/sync-roster/{team_id}")
def sync_single_roster(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Sync roster for a single team."""
    team = db.query(Team).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    count = sync_team_roster(db, team)
    db.commit()
    return {"status": "ok", "teamId": team_id, "playersUpserted": count}


@router.post("/players/ingest-games")
def ingest_games(
    date: str = Query(..., description="Date in YYYYMMDD format"),
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """Ingest box scores for all completed games on a date."""
    result = ingest_date_box_scores(db, date, gender)
    return {"status": "ok", "date": date, "gender": gender, **result}


@router.post("/players/recompute-stats")
def recompute_stats(
    gender: str = Query("M", pattern="^(M|W)$"),
    team_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Recompute season averages from game logs."""
    count = recompute_season_stats(db, team_id, gender)
    db.commit()
    return {"status": "ok", "playersUpdated": count}


@router.post("/players/compute-importance/{team_id}")
def compute_importance(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Compute player importance scores for a team."""
    count = compute_importance_scores(db, team_id)
    db.commit()
    return {"status": "ok", "teamId": team_id, "playersScored": count}


@router.post("/players/full-sync")
def full_sync(
    date: str = Query(..., description="Date in YYYYMMDD format"),
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """Full pipeline: sync rosters → ingest box scores → recompute stats → compute importance.

    This is the daily cron endpoint. Call it with yesterday's date.
    """
    # 1. Sync all rosters
    roster_result = sync_all_rosters(db, gender)

    # 2. Ingest box scores
    ingest_result = ingest_date_box_scores(db, date, gender)

    # 3. Recompute season averages
    stats_count = recompute_season_stats(db, gender=gender)
    db.commit()

    # 4. Compute importance for all teams that had games
    # (importance scores need updated season stats first)
    teams_with_players = (
        db.query(PlayerSeasonStats.team_id)
        .filter(PlayerSeasonStats.season == SEASON)
        .distinct()
        .all()
    )
    importance_count = 0
    for (tid,) in teams_with_players:
        importance_count += compute_importance_scores(db, tid)
    db.commit()

    return {
        "status": "ok",
        "date": date,
        "gender": gender,
        "rosters": roster_result,
        "boxScores": ingest_result,
        "statsRecomputed": stats_count,
        "importanceScored": importance_count,
    }
