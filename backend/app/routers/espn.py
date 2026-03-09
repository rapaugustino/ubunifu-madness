"""Live data endpoints powered by ESPN API, enriched with our DB data."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, EloRating, Prediction, TourneySeed, TeamConference, TeamSeasonStats
from app.services import espn

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

        # Add our model's win probability if both teams are in our DB
        away_kid = game["away"].get("kaggleId")
        home_kid = game["home"].get("kaggleId")
        game["winProb"] = None
        if away_kid and home_kid:
            lo, hi = min(away_kid, home_kid), max(away_kid, home_kid)
            pred = (
                db.query(Prediction)
                .filter(Prediction.season == SEASON, Prediction.team_a_id == lo, Prediction.team_b_id == hi)
                .first()
            )
            if pred:
                # winProb is for the away team
                prob = pred.win_prob_a if away_kid == lo else (1 - pred.win_prob_a)
                game["winProb"] = {"away": round(prob, 3), "home": round(1 - prob, 3)}

    return {"games": games, "date": date, "gender": gender}


@router.get("/scores/{game_id}")
def game_box_score(game_id: str):
    """Full box score for a game."""
    return espn.get_game_summary(game_id)


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
        if existing:
            existing.seed_number = int(seed_num)
        else:
            db.add(TourneySeed(
                season=season,
                team_id=db_team.id,
                seed_number=int(seed_num),
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
