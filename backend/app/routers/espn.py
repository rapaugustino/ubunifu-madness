"""Live data endpoints powered by ESPN API, enriched with our DB data."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, EloRating, TourneySeed, TeamSeasonStats, GamePrediction, GameResult
from app.services import espn
from app.services.predictor import predict_matchup, explain_matchup

router = APIRouter(tags=["espn"])

SEASON = 2026


def _espn_to_kaggle_map(db: Session, gender: str | None = None) -> dict[int, Team]:
    """Build espn_id → Team lookup."""
    q = db.query(Team).filter(Team.espn_id.isnot(None))
    if gender:
        q = q.filter(Team.gender == gender)
    return {t.espn_id: t for t in q.all()}


def _enrich_team(team_espn: dict, espn_map: dict, elo_map: dict) -> dict:
    """Add Kaggle ID and Elo to an ESPN team dict."""
    espn_id = team_espn.get("espnId")
    db_team = espn_map.get(espn_id)
    team_espn["kaggleId"] = db_team.id if db_team else None
    team_espn["elo"] = round(elo_map.get(db_team.id, 0), 1) if db_team and db_team.id in elo_map else None
    return team_espn


@router.get("/scores")
def live_scores(
    date: str | None = None,
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """Today's games with Elo enrichment and win probabilities."""
    games = espn.get_scoreboard(date, gender)

    espn_map = _espn_to_kaggle_map(db, gender)
    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating).filter(EloRating.season == SEASON).all()
    }

    for game in games:
        _enrich_team(game["away"], espn_map, elo_map)
        _enrich_team(game["home"], espn_map, elo_map)

        away_kid = game["away"].get("kaggleId")
        home_kid = game["home"].get("kaggleId")
        game["winProb"] = None
        game["lockedPrediction"] = None

        if away_kid and home_kid:
            espn_gid = str(game["id"])
            date_str = date or datetime.now().strftime("%Y%m%d")

            # Detect game type from ESPN data
            game_type = game.get("gameType", "regular")
            headline = game.get("headline") or ""
            if game_type == "tourney":
                detected_type = "tourney"
            elif game_type == "conf_tourney" or "conference" in headline.lower():
                detected_type = "conf_tourney"
            else:
                detected_type = "regular"

            is_conf_tourney = detected_type == "conf_tourney"

            # Check for existing locked prediction
            locked = (
                db.query(GamePrediction)
                .filter(GamePrediction.espn_game_id == espn_gid)
                .first()
            )

            if not locked:
                # Lock in a prediction for this game (pre-game)
                prob_away, source = predict_matchup(
                    db, away_kid, home_kid, is_conf_tourney=is_conf_tourney
                )
                expl = explain_matchup(db, away_kid, home_kid, prob_a=prob_away, is_conf_tourney=is_conf_tourney)
                locked = GamePrediction(
                    espn_game_id=espn_gid,
                    game_date=date_str,
                    season=SEASON,
                    gender=gender,
                    away_team_id=away_kid,
                    home_team_id=home_kid,
                    away_name=game["away"].get("name"),
                    home_name=game["home"].get("name"),
                    locked_prob_away=prob_away,
                    prediction_source=source,
                    explanation=expl,
                    game_type=detected_type,
                )
                db.add(locked)
                db.flush()

            # Resolve outcome if game is final and not yet resolved
            is_final = game["status"] == "STATUS_FINAL"
            if is_final and locked.model_correct is None:
                away_score = game["away"].get("score", 0)
                home_score = game["home"].get("score", 0)
                if away_score != home_score:  # skip ties (shouldn't happen in basketball)
                    model_picked_away = locked.locked_prob_away > 0.5
                    actual_away_won = away_score > home_score
                    locked.away_score = away_score
                    locked.home_score = home_score
                    locked.winner_team_id = away_kid if actual_away_won else home_kid
                    locked.model_correct = (model_picked_away == actual_away_won)
                    locked.resolved_at = datetime.utcnow()
                    db.flush()

            # Return locked prediction to frontend
            game["winProb"] = {
                "away": round(locked.locked_prob_away, 3),
                "home": round(1 - locked.locked_prob_away, 3),
            }
            game["lockedPrediction"] = {
                "probAway": round(locked.locked_prob_away, 3),
                "probHome": round(1 - locked.locked_prob_away, 3),
                "source": locked.prediction_source,
                "explanation": locked.explanation or "",
                "lockedAt": locked.locked_at.isoformat() if locked.locked_at else None,
                "resolved": locked.model_correct is not None,
                "correct": locked.model_correct,
            }

    try:
        db.commit()
    except Exception:
        db.rollback()

    return {"games": games, "date": date, "gender": gender}


@router.get("/scores/{game_id}")
def game_box_score(game_id: str, gender: str = Query("M", pattern="^(M|W)$")):
    """Full box score for a game."""
    try:
        return espn.get_game_summary(game_id, gender)
    except Exception:
        raise HTTPException(404, f"Game {game_id} not found on ESPN")


@router.get("/rankings/ap")
def ap_rankings(
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """AP Top 25 enriched with our Elo ratings."""
    rankings = espn.get_rankings(gender)

    espn_map = _espn_to_kaggle_map(db, gender)
    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating)
        .filter(EloRating.season == SEASON)
        .all()
    }

    for entry in rankings:
        espn_id = entry["team"].get("espnId")
        db_team = espn_map.get(espn_id)
        entry["team"]["kaggleId"] = db_team.id if db_team else None
        entry["team"]["elo"] = round(elo_map.get(db_team.id, 0), 1) if db_team and db_team.id in elo_map else None

    return {"rankings": rankings, "gender": gender}


@router.get("/schedule/{team_id}")
def team_schedule(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Team schedule by Kaggle team ID."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team or not team.espn_id:
        raise HTTPException(404, "Team not found or no ESPN mapping")

    schedule = espn.get_team_schedule(team.espn_id, team.gender)
    return {"teamId": team_id, "teamName": team.name, "schedule": schedule}


@router.get("/roster/{team_id}")
def team_roster(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Get team roster with players and coach by Kaggle team ID."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team or not team.espn_id:
        raise HTTPException(404, "Team not found or no ESPN mapping")

    roster = espn.get_roster(team.espn_id, team.gender)
    return {"teamId": team_id, "teamName": team.name, **roster}


@router.get("/history/{team_a_id}/{team_b_id}")
def head_to_head_history(
    team_a_id: int,
    team_b_id: int,
    limit: int = Query(5, le=20),
    db: Session = Depends(get_db),
):
    """Head-to-head game history between two teams."""
    from sqlalchemy import or_, and_

    team_a = db.query(Team).filter(Team.id == team_a_id).first()
    team_b = db.query(Team).filter(Team.id == team_b_id).first()
    if not team_a or not team_b:
        raise HTTPException(404, "One or both teams not found")

    games = (
        db.query(GameResult)
        .filter(
            or_(
                and_(GameResult.w_team_id == team_a_id, GameResult.l_team_id == team_b_id),
                and_(GameResult.w_team_id == team_b_id, GameResult.l_team_id == team_a_id),
            )
        )
        .order_by(GameResult.season.desc(), GameResult.day_num.desc())
        .limit(limit)
        .all()
    )

    team_names = {team_a.id: team_a.name, team_b.id: team_b.name}

    meetings = []
    for g in games:
        loc_label = {"H": "home", "A": "away", "N": "neutral"}.get(g.w_loc, "unknown")
        meetings.append({
            "season": g.season,
            "dayNum": g.day_num,
            "winnerName": team_names[g.w_team_id],
            "loserName": team_names[g.l_team_id],
            "winnerScore": g.w_score,
            "loserScore": g.l_score,
            "winnerLoc": loc_label,
            "gameType": g.game_type,
            "numOt": g.num_ot,
        })

    return {
        "teamA": {"id": team_a.id, "name": team_a.name},
        "teamB": {"id": team_b.id, "name": team_b.name},
        "meetings": meetings,
        "count": len(meetings),
    }


@router.post("/seeds/refresh")
def refresh_seeds(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = SEASON,
    db: Session = Depends(get_db),
):
    """Fetch tournament seeds from ESPN and upsert into tourney_seeds table.

    Call this after Selection Sunday to populate the bracket for the new season.
    """
    espn_teams = espn.get_tournament_teams(gender)
    if not espn_teams:
        return {"status": "no_data", "message": "No tournament data available from ESPN yet", "count": 0}

    # Map ESPN IDs to our team IDs
    espn_map = _espn_to_kaggle_map(db, gender)

    inserted = 0
    skipped = 0
    for et in espn_teams:
        db_team = espn_map.get(et["espnId"])
        if not db_team:
            skipped += 1
            continue

        seed_num = et.get("seed")
        if seed_num is None:
            skipped += 1
            continue

        # Upsert: check if seed already exists
        existing = (
            db.query(TourneySeed)
            .filter(
                TourneySeed.season == season,
                TourneySeed.team_id == db_team.id,
            )
            .first()
        )
        seed_int = int(seed_num)
        # Derive region from insertion order (W, X, Y, Z for groups of 16)
        region = et.get("region", "W")
        seed_str = f"{region}{seed_int:02d}"

        if existing:
            existing.seed_number = seed_int
            existing.seed = seed_str
            existing.region = region
        else:
            db.add(TourneySeed(
                season=season,
                team_id=db_team.id,
                seed=seed_str,
                seed_number=seed_int,
                region=region,
            ))
        inserted += 1

    db.commit()
    return {
        "status": "ok",
        "season": season,
        "gender": gender,
        "inserted": inserted,
        "skipped": skipped,
    }


@router.post("/elo/refresh")
def refresh_elo(
    date: str | None = None,
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """Update Elo ratings from ESPN game results for a given date.

    Fetches completed games, applies Elo updates, and refreshes conference strength.
    Idempotent — skips games already in the database.
    """
    from datetime import datetime, timedelta
    from scripts.update_elo_live import update_elo_from_espn, refresh_conference_strength

    dates = []
    if date:
        dates.append(date)
    else:
        today = datetime.now()
        dates.append(today.strftime("%Y%m%d"))
        dates.append((today - timedelta(days=1)).strftime("%Y%m%d"))

    all_results = []
    total_processed = 0
    for d in dates:
        result = update_elo_from_espn(db, d, gender)
        total_processed += result["games_processed"]
        all_results.append(result)

    conf_updated = 0
    if total_processed > 0:
        conf_updated = refresh_conference_strength(db, gender)

    return {
        "status": "ok",
        "gender": gender,
        "total_games_processed": total_processed,
        "conferences_updated": conf_updated,
        "details": all_results,
    }


@router.post("/records/refresh")
def refresh_records(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = SEASON,
    db: Session = Depends(get_db),
):
    """Update team win/loss records from ESPN for all mapped teams.

    Fetches each team's current record individually from ESPN.
    """
    espn_map = _espn_to_kaggle_map(db, gender)

    updated = 0
    failed = 0
    for espn_id, db_team in espn_map.items():
        rec = espn.get_team_record(espn_id, gender)
        if not rec:
            failed += 1
            continue

        stats = (
            db.query(TeamSeasonStats)
            .filter(TeamSeasonStats.season == season, TeamSeasonStats.team_id == db_team.id)
            .first()
        )
        if stats:
            stats.wins = rec["wins"]
            stats.losses = rec["losses"]
            total = rec["wins"] + rec["losses"]
            stats.win_pct = rec["wins"] / total if total > 0 else 0
            updated += 1

    db.commit()
    return {
        "status": "ok",
        "season": season,
        "gender": gender,
        "updated": updated,
        "failed": failed,
    }
