"""
Backfill missing game results and Elo updates for the current season.

Iterates through every date from season start (Nov 4) to today,
fetching ESPN scoreboards and processing any games not already in GameResult.
Safe to run multiple times — deduplication is built in.

Run from backend/:
    python -m scripts.backfill_games [--start YYYYMMDD]
"""

import sys
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from scripts.update_elo_live import update_elo_from_espn, refresh_conference_strength


SEASON = 2026
DEFAULT_START = "20251104"


def run(start_date: str = DEFAULT_START):
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.now()
    total_days = (end - start).days + 1

    print(f"=== Backfill: {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} ({total_days} days) ===")

    total_games = {"M": 0, "W": 0}
    current = start

    while current <= end:
        date_str = current.strftime("%Y%m%d")

        # Fresh session per day to avoid connection timeouts
        session = SessionLocal()
        try:
            for gender in ["M", "W"]:
                result = update_elo_from_espn(session, date_str, gender)
                if result["games_processed"] > 0:
                    total_games[gender] += result["games_processed"]
                    print(f"  {date_str} [{gender}]: {result['games_processed']} new games")
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"  {date_str}: ERROR - {e}")
        finally:
            session.close()

        current += timedelta(days=1)
        # Small delay to be polite to ESPN
        time.sleep(0.1)

    # Final pass: refresh conference strength
    session = SessionLocal()
    try:
        for gender in ["M", "W"]:
            label = "Men's" if gender == "M" else "Women's"
            if total_games[gender] > 0:
                conf_count = refresh_conference_strength(session, gender)
                session.commit()
                print(f"\n[{label}] {total_games[gender]} total new games, {conf_count} conferences refreshed")
            else:
                print(f"\n[{label}] No new games found")
    finally:
        session.close()

    print("\n=== Backfill complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill missing game results")
    parser.add_argument("--start", default=DEFAULT_START, help="Start date (YYYYMMDD)")
    args = parser.parse_args()
    run(args.start)
