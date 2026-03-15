"""
Backfill player box scores and season stats for the entire 2026 season.

Iterates through every date from season start (Nov 4, 2025) to today,
ingesting box scores from ESPN for completed games. Then recomputes
season averages and importance scores for all players.

Run from backend/:
    python -m scripts.backfill_player_stats
    python -m scripts.backfill_player_stats --gender M
    python -m scripts.backfill_player_stats --from 20260101
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import PlayerSeasonStats
from app.services.player_sync import (
    sync_all_rosters,
    ingest_date_box_scores,
    recompute_season_stats,
    compute_importance_scores,
)

SEASON = 2026
SEASON_START = "20251104"  # NCAA season typically starts first Tuesday in November


def date_range(start: str, end: str):
    d = datetime.strptime(start, "%Y%m%d")
    end_d = datetime.strptime(end, "%Y%m%d")
    while d <= end_d:
        yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(description="Backfill player box scores")
    parser.add_argument("--from", dest="from_date", default=SEASON_START,
                        help="Start date YYYYMMDD (default: season start)")
    parser.add_argument("--to", dest="to_date",
                        default=datetime.now().strftime("%Y%m%d"),
                        help="End date YYYYMMDD (default: today)")
    parser.add_argument("--gender", default="both", choices=["M", "W", "both"])
    parser.add_argument("--skip-roster-sync", action="store_true",
                        help="Skip roster sync (faster if rosters already exist)")
    args = parser.parse_args()

    genders = ["M", "W"] if args.gender == "both" else [args.gender]
    dates = list(date_range(args.from_date, args.to_date))
    print(f"Backfilling player stats: {len(dates)} days "
          f"({args.from_date} -> {args.to_date}) for {', '.join(genders)}")

    for gender in genders:
        label = "Men's" if gender == "M" else "Women's"

        # Step 1: Sync rosters (ensures Player records exist)
        if not args.skip_roster_sync:
            print(f"\n[{label}] Syncing rosters from ESPN...")
            session = SessionLocal()
            try:
                roster_result = sync_all_rosters(session, gender)
                session.commit()
                print(f"[{label}] Rosters: {roster_result}")
            except Exception as e:
                session.rollback()
                print(f"[{label}] Roster sync error: {e}")
            finally:
                session.close()

        # Step 2: Ingest box scores — fresh session per date for resilience
        print(f"\n[{label}] Ingesting box scores...")
        total_games = 0
        total_logs = 0
        errors = 0
        for i, date_str in enumerate(dates):
            session = SessionLocal()
            try:
                result = ingest_date_box_scores(session, date_str, gender)
                if result["games_processed"] > 0:
                    total_games += result["games_processed"]
                    total_logs += result["player_logs_created"]
                    print(f"  {date_str}: {result['games_processed']} games, "
                          f"{result['player_logs_created']} player logs")
            except Exception as e:
                errors += 1
                session.rollback()
                print(f"  {date_str}: ERROR - {e}")
            finally:
                session.close()

            # Progress every 20 days
            if (i + 1) % 20 == 0:
                print(f"  ... {i + 1}/{len(dates)} days processed")

        print(f"[{label}] Box scores: {total_games} games, {total_logs} player logs"
              + (f", {errors} errors" if errors else ""))

        # Step 3: Recompute season averages
        print(f"\n[{label}] Recomputing season stats...")
        session = SessionLocal()
        try:
            stats_count = recompute_season_stats(session, gender=gender)
            session.commit()
            print(f"[{label}] Updated stats for {stats_count} players")

            # Step 4: Compute importance scores
            print(f"[{label}] Computing importance scores...")
            team_ids = (
                session.query(PlayerSeasonStats.team_id)
                .filter(PlayerSeasonStats.season == SEASON)
                .distinct()
                .all()
            )
            importance_count = 0
            for (tid,) in team_ids:
                importance_count += compute_importance_scores(session, tid)
            session.commit()
            print(f"[{label}] Importance scores for {importance_count} players")
        except Exception as e:
            session.rollback()
            print(f"[{label}] Stats recompute error: {e}")
        finally:
            session.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
