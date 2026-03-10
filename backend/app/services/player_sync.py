"""Player data sync service — roster + box score ingestion from ESPN.

Responsibilities:
1. Sync team rosters (players table) from ESPN
2. Ingest box score stats from completed games into player_game_logs
3. Recompute season averages in player_season_stats
4. Compute player importance scores for injury impact modeling
"""

import logging

from sqlalchemy.orm import Session

from app.models import Team, Player, PlayerSeasonStats, PlayerGameLog
from app.services import espn

logger = logging.getLogger(__name__)

SEASON = 2026


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------

def _parse_minutes(mins_str: str) -> float:
    """Parse ESPN minutes string (e.g. '33', '28:30') to float."""
    if not mins_str or mins_str == '--':
        return 0.0
    try:
        if ':' in mins_str:
            parts = mins_str.split(':')
            return float(parts[0]) + float(parts[1]) / 60
        return float(mins_str)
    except (ValueError, IndexError):
        return 0.0


def _parse_made_att(val: str) -> tuple[int, int]:
    """Parse '3-7' format into (made, attempted)."""
    if not val or val == '--':
        return 0, 0
    try:
        parts = val.split('-')
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 0, 0


def _safe_int(val: str) -> int:
    if not val or val == '--':
        return 0
    try:
        return int(val)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Roster sync
# ---------------------------------------------------------------------------

def sync_team_roster(db: Session, team: Team) -> int:
    """Sync roster for a single team from ESPN. Returns count of players upserted."""
    if not team.espn_id:
        return 0

    roster_data = espn.get_roster(team.espn_id, team.gender)
    players = roster_data.get("players", [])
    count = 0

    for p in players:
        espn_id = int(p.get("id", 0))
        if not espn_id:
            continue

        existing = db.query(Player).filter(Player.espn_id == espn_id).first()
        if existing:
            existing.team_id = team.id
            existing.name = p.get("name", existing.name)
            existing.jersey = p.get("jersey")
            existing.position = p.get("position")
            existing.position_full = p.get("positionFull")
            existing.height = p.get("height")
            existing.weight = p.get("weight")
            existing.experience = p.get("experience")
            existing.headshot_url = p.get("headshot")
            existing.gender = team.gender
        else:
            db.add(Player(
                espn_id=espn_id,
                team_id=team.id,
                name=p.get("name", "Unknown"),
                jersey=p.get("jersey"),
                position=p.get("position"),
                position_full=p.get("positionFull"),
                height=p.get("height"),
                weight=p.get("weight"),
                experience=p.get("experience"),
                headshot_url=p.get("headshot"),
                gender=team.gender,
            ))
        count += 1

    db.flush()
    return count


def sync_all_rosters(db: Session, gender: str = "M") -> dict:
    """Sync rosters for all teams with ESPN mappings."""
    teams = db.query(Team).filter(Team.espn_id.isnot(None), Team.gender == gender).all()
    total = 0
    synced_teams = 0

    for team in teams:
        try:
            n = sync_team_roster(db, team)
            total += n
            if n > 0:
                synced_teams += 1
        except Exception as e:
            logger.warning(f"Failed to sync roster for {team.name}: {e}")

    db.commit()
    return {"teams_synced": synced_teams, "players_upserted": total}


# ---------------------------------------------------------------------------
# Box score ingestion
# ---------------------------------------------------------------------------

def ingest_game_box_score(db: Session, espn_game_id: str, game_date: str, gender: str = "M") -> int:
    """Ingest player stats from a completed game's box score. Returns count of logs created."""
    summary = espn.get_game_summary(espn_game_id, gender)
    # get_game_summary returns flat {"players": [...]} list
    player_list = summary.get("players", [])

    if not player_list:
        return 0

    count = 0

    for p_data in player_list:
        player_espn_id = p_data.get("espnId")
        if not player_espn_id:
            continue

        stat_map = p_data.get("stats", {})
        if not stat_map:
            continue

        # Upper-case keys for consistency
        stat_map = {k.upper(): v for k, v in stat_map.items()}

        # Find or create player in our DB
        player = db.query(Player).filter(Player.espn_id == player_espn_id).first()
        if not player:
            player = Player(
                espn_id=player_espn_id,
                name=p_data.get("name", "Unknown"),
                position=p_data.get("position"),
                gender=gender,
            )
            db.add(player)
            db.flush()

        # Skip if game log already exists
        existing = db.query(PlayerGameLog).filter(
            PlayerGameLog.player_id == player.id,
            PlayerGameLog.espn_game_id == espn_game_id,
        ).first()
        if existing:
            continue

        # Parse stats
        fg_m, fg_a = _parse_made_att(stat_map.get("FG", ""))
        fg3_m, fg3_a = _parse_made_att(stat_map.get("3PT", ""))
        ft_m, ft_a = _parse_made_att(stat_map.get("FT", ""))

        log = PlayerGameLog(
            player_id=player.id,
            espn_game_id=espn_game_id,
            game_date=game_date,
            season=SEASON,
            minutes=_parse_minutes(stat_map.get("MIN", "")),
            points=_safe_int(stat_map.get("PTS", "")),
            fgm=fg_m,
            fga=fg_a,
            fgm3=fg3_m,
            fga3=fg3_a,
            ftm=ft_m,
            fta=ft_a,
            oreb=_safe_int(stat_map.get("OREB", "")),
            dreb=_safe_int(stat_map.get("DREB", "")),
            reb=_safe_int(stat_map.get("REB", "")),
            ast=_safe_int(stat_map.get("AST", "")),
            to=_safe_int(stat_map.get("TO", "")),
            stl=_safe_int(stat_map.get("STL", "")),
            blk=_safe_int(stat_map.get("BLK", "")),
            pf=_safe_int(stat_map.get("PF", "")),
        )
        db.add(log)
        count += 1

    db.flush()
    return count


def ingest_date_box_scores(db: Session, date: str, gender: str = "M") -> dict:
    """Ingest box scores for all completed games on a date."""
    games = espn.get_scoreboard(date, gender)
    total_logs = 0
    games_processed = 0

    for game in games:
        status = game.get("status", "")
        if status != "STATUS_FINAL":
            continue

        espn_game_id = str(game.get("id", ""))
        if not espn_game_id:
            continue

        try:
            n = ingest_game_box_score(db, espn_game_id, date, gender)
            total_logs += n
            if n > 0:
                games_processed += 1
        except Exception as e:
            logger.warning(f"Failed to ingest box score for game {espn_game_id}: {e}")

    db.commit()
    return {"games_processed": games_processed, "player_logs_created": total_logs}


# ---------------------------------------------------------------------------
# Recompute season averages
# ---------------------------------------------------------------------------

def recompute_season_stats(db: Session, team_id: int | None = None, gender: str = "M") -> int:
    """Recompute PlayerSeasonStats from PlayerGameLogs. Returns count updated."""
    # Get all players with game logs this season
    query = (
        db.query(PlayerGameLog.player_id)
        .filter(PlayerGameLog.season == SEASON)
        .distinct()
    )

    if team_id:
        player_ids = [p.id for p in db.query(Player).filter(Player.team_id == team_id).all()]
        if player_ids:
            query = query.filter(PlayerGameLog.player_id.in_(player_ids))

    player_ids_with_logs = [r[0] for r in query.all()]
    count = 0

    for pid in player_ids_with_logs:
        player = db.query(Player).get(pid)
        if not player or not player.team_id:
            continue

        logs = (
            db.query(PlayerGameLog)
            .filter(PlayerGameLog.player_id == pid, PlayerGameLog.season == SEASON)
            .all()
        )
        if not logs:
            continue

        gp = len(logs)
        mins = sum(log.minutes for log in logs)
        pts = sum(log.points for log in logs)
        fgm = sum(log.fgm for log in logs)
        fga = sum(log.fga for log in logs)
        fgm3 = sum(log.fgm3 for log in logs)
        fga3 = sum(log.fga3 for log in logs)
        ftm = sum(log.ftm for log in logs)
        fta = sum(log.fta for log in logs)
        oreb = sum(log.oreb for log in logs)
        dreb = sum(log.dreb for log in logs)
        reb = sum(log.reb for log in logs)
        ast = sum(log.ast for log in logs)
        to_total = sum(log.to for log in logs)
        stl = sum(log.stl for log in logs)
        blk = sum(log.blk for log in logs)
        pf = sum(log.pf for log in logs)

        # Upsert season stats
        ss = (
            db.query(PlayerSeasonStats)
            .filter(PlayerSeasonStats.season == SEASON, PlayerSeasonStats.player_id == pid)
            .first()
        )
        if not ss:
            ss = PlayerSeasonStats(season=SEASON, player_id=pid, team_id=player.team_id)
            db.add(ss)

        ss.team_id = player.team_id
        ss.games_played = gp
        ss.minutes_total = mins
        ss.points_total = pts
        ss.fgm = fgm
        ss.fga = fga
        ss.fgm3 = fgm3
        ss.fga3 = fga3
        ss.ftm = ftm
        ss.fta = fta
        ss.oreb_total = oreb
        ss.dreb_total = dreb
        ss.reb_total = reb
        ss.ast_total = ast
        ss.to_total = to_total
        ss.stl_total = stl
        ss.blk_total = blk
        ss.pf_total = pf

        # Averages
        ss.ppg = round(pts / gp, 1) if gp else 0
        ss.rpg = round(reb / gp, 1) if gp else 0
        ss.apg = round(ast / gp, 1) if gp else 0
        ss.mpg = round(mins / gp, 1) if gp else 0
        ss.fg_pct = round(fgm / fga, 3) if fga > 0 else None
        ss.fg3_pct = round(fgm3 / fga3, 3) if fga3 > 0 else None
        ss.ft_pct = round(ftm / fta, 3) if fta > 0 else None

        count += 1

    db.flush()
    return count


# ---------------------------------------------------------------------------
# Player importance scoring
# ---------------------------------------------------------------------------

def compute_importance_scores(db: Session, team_id: int) -> int:
    """Compute importance scores for all players on a team.

    Importance is based on:
    - Minutes share (what % of team minutes does this player get)
    - Scoring share (what % of team points does this player score)
    - Combined into a 0-1 score

    A player with importance_score > 0.15 is a "key player" whose absence
    would meaningfully impact team performance.
    """
    stats = (
        db.query(PlayerSeasonStats)
        .filter(PlayerSeasonStats.season == SEASON, PlayerSeasonStats.team_id == team_id)
        .all()
    )
    if not stats:
        return 0

    total_minutes = sum(s.minutes_total for s in stats) or 1
    total_points = sum(s.points_total for s in stats) or 1

    for s in stats:
        mins_share = s.minutes_total / total_minutes
        pts_share = s.points_total / total_points

        s.minutes_share = round(mins_share, 4)
        # Usage rate approximation: (FGA + 0.44*FTA + TO) / team_possessions
        # Simplified: pts_share * 0.6 + mins_share * 0.4
        s.usage_rate = round(pts_share * 0.6 + mins_share * 0.4, 4)
        # Importance: weighted combination
        s.importance_score = round(mins_share * 0.4 + pts_share * 0.4 + (s.rpg or 0) / 15.0 * 0.1 + (s.apg or 0) / 10.0 * 0.1, 4)

    db.flush()
    return len(stats)
