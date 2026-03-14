"""Delete old predictions from a cutoff date and regenerate them with the current model.

This script:
1. Deletes GamePrediction records from the cutoff date onward
2. Re-fetches each date's scores via the ESPN service
3. Creates new locked predictions using the current predictor (ml_ensemble)
4. Resolves outcomes for completed games

Usage:
    cd backend
    python3 -m scripts.regenerate_predictions --from-date 20260308
    python3 -m scripts.regenerate_predictions --from-date 20260308 --dry-run
"""

import argparse
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import GamePrediction, Team
from app.services import espn
from app.services.predictor import predict_matchup, explain_matchup, reload_model_bundle

SEASON = 2026


def main():
    parser = argparse.ArgumentParser(description="Regenerate predictions from a cutoff date")
    parser.add_argument("--from-date", required=True, help="Cutoff date YYYYMMDD (inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without changing DB")
    parser.add_argument("--gender", default=None, help="Filter by gender (M or W), default: both")
    args = parser.parse_args()

    cutoff = args.from_date
    dry_run = args.dry_run

    # Validate date format
    try:
        datetime.strptime(cutoff, "%Y%m%d")
    except ValueError:
        print(f"ERROR: Invalid date format '{cutoff}'. Use YYYYMMDD.")
        sys.exit(1)

    db = SessionLocal()

    # Force reload model artifacts to pick up latest
    reload_model_bundle()

    # Step 1: Count and show what will be deleted
    query = db.query(GamePrediction).filter(GamePrediction.game_date >= cutoff)
    if args.gender:
        query = query.filter(GamePrediction.gender == args.gender)

    old_predictions = query.all()
    print(f"Found {len(old_predictions)} predictions from {cutoff} onward")

    if old_predictions:
        sources = {}
        resolved_count = 0
        for gp in old_predictions:
            sources[gp.prediction_source] = sources.get(gp.prediction_source, 0) + 1
            if gp.model_correct is not None:
                resolved_count += 1

        print(f"  Sources: {sources}")
        print(f"  Resolved (have outcomes): {resolved_count}")
        print(f"  Unresolved: {len(old_predictions) - resolved_count}")

        # Collect unique dates
        dates = sorted(set(gp.game_date for gp in old_predictions))
        print(f"  Date range: {dates[0]} to {dates[-1]} ({len(dates)} days)")

    if dry_run:
        print("\n[DRY RUN] Would delete these predictions and regenerate. Run without --dry-run to execute.")
        db.close()
        return

    if not old_predictions:
        print("Nothing to regenerate.")
        db.close()
        return

    # Step 2: Delete old predictions
    deleted = query.delete()
    db.commit()
    print(f"\nDeleted {deleted} old predictions.")

    # Step 3: Regenerate by fetching each date from ESPN
    # Build ESPN-to-Kaggle ID maps
    genders = [args.gender] if args.gender else ["M", "W"]

    # Build date range from cutoff to today
    start = datetime.strptime(cutoff, "%Y%m%d")
    end = datetime.now()
    all_dates = []
    current = start
    while current <= end:
        all_dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)

    print(f"\nRegenerating predictions for {len(all_dates)} dates × {len(genders)} genders...")

    total_created = 0
    total_resolved = 0
    total_errors = 0

    for gender in genders:
        # Build lookups
        espn_map = {}
        for t in db.query(Team).filter(Team.espn_id.isnot(None), Team.gender == gender).all():
            espn_map[t.espn_id] = t

        for date_str in all_dates:
            try:
                games = espn.get_scoreboard(date_str, gender)
            except Exception as e:
                print(f"  ESPN error {date_str} {gender}: {e}")
                total_errors += 1
                continue

            day_created = 0
            day_resolved = 0

            for game in games:
                espn_gid = str(game["id"])

                # Get Kaggle IDs
                away_espn = game["away"].get("espnId")
                home_espn = game["home"].get("espnId")
                away_team = espn_map.get(away_espn)
                home_team = espn_map.get(home_espn)

                if not away_team or not home_team:
                    continue

                away_kid = away_team.id
                home_kid = home_team.id

                # Check if prediction already exists (shouldn't, but be safe)
                existing = db.query(GamePrediction).filter(
                    GamePrediction.espn_game_id == espn_gid
                ).first()
                if existing:
                    continue

                # Detect game type
                game_type_raw = game.get("gameType", "regular")
                headline = game.get("headline") or ""
                if game_type_raw == "tourney":
                    detected_type = "tourney"
                elif game_type_raw == "conf_tourney" or "conference" in headline.lower():
                    detected_type = "conf_tourney"
                else:
                    detected_type = "regular"

                is_conf_tourney = detected_type == "conf_tourney"

                # Generate prediction
                try:
                    prob_away, source = predict_matchup(
                        db, away_kid, home_kid, is_conf_tourney=is_conf_tourney
                    )
                    expl = explain_matchup(
                        db, away_kid, home_kid, prob_a=prob_away, is_conf_tourney=is_conf_tourney
                    )
                except Exception as e:
                    print(f"    Predict error {away_kid} vs {home_kid}: {e}")
                    total_errors += 1
                    continue

                gp = GamePrediction(
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

                # Resolve outcome if game is final
                is_final = game.get("status") == "STATUS_FINAL"
                if is_final:
                    away_score = game["away"].get("score", 0)
                    home_score = game["home"].get("score", 0)
                    if away_score != home_score:
                        model_picked_away = prob_away > 0.5
                        actual_away_won = away_score > home_score
                        gp.away_score = away_score
                        gp.home_score = home_score
                        gp.winner_team_id = away_kid if actual_away_won else home_kid
                        gp.model_correct = (model_picked_away == actual_away_won)
                        gp.resolved_at = datetime.utcnow()
                        day_resolved += 1

                db.add(gp)
                day_created += 1

            if day_created > 0:
                db.flush()
                print(f"  {date_str} {gender}: {day_created} predictions, {day_resolved} resolved")

            total_created += day_created
            total_resolved += day_resolved

    db.commit()

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")
    print(f"Created:  {total_created} predictions")
    print(f"Resolved: {total_resolved} outcomes")
    print(f"Errors:   {total_errors}")
    print("Source:   all predictions use current predictor (ml_ensemble)")

    db.close()


if __name__ == "__main__":
    main()
