"""
Backfill game results from ESPN for a specific date range.

Loops through each date, fetching completed games and ingesting any that
are missing from the game_results table. Also updates Elo, W/L records,
conference strength, and SOS.

When to run: one-time catch-up when the daily cron missed days, or when
bootstrapping a new deployment with historical game data.

Run from backend/:
    python -m scripts.backfill_espn_games --from 20251101 --to 20260309
    python -m scripts.backfill_espn_games --from 20260201 --to 20260210 --gender M
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import defaultdict

from app.database import SessionLocal
from app.models import GameResult, TeamSeasonStats
from scripts.update_elo_live import update_elo_from_espn, refresh_conference_strength
from scripts.cron_elo_update import refresh_sos

SEASON = 2026


def recompute_records(session, gender: str) -> int:
    """Recompute W/L records from game_results to fix any double-counting."""
    wins: dict[int, int] = defaultdict(int)
    losses: dict[int, int] = defaultdict(int)

    games = session.query(GameResult).filter(
        GameResult.season == SEASON, GameResult.gender == gender
    ).all()
    for g in games:
        wins[g.w_team_id] += 1
        losses[g.l_team_id] += 1

    stats = session.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON).all()
    fixed = 0
    for s in stats:
        w = wins.get(s.team_id, 0)
        loss_count = losses.get(s.team_id, 0)
        if w == 0 and loss_count == 0:
            continue
        total = w + loss_count
        wp = round(w / total, 4) if total > 0 else 0
        if s.wins != w or s.losses != loss_count:
            s.wins = w
            s.losses = loss_count
            s.win_pct = wp
            fixed += 1

    session.flush()
    return fixed


def date_range(start: str, end: str):
    """Generate YYYYMMDD strings from start to end (inclusive)."""
    d = datetime.strptime(start, "%Y%m%d")
    end_d = datetime.strptime(end, "%Y%m%d")
    while d <= end_d:
        yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(description="Backfill ESPN game results")
    parser.add_argument("--from", dest="from_date", required=True,
                        help="Start date YYYYMMDD")
    parser.add_argument("--to", dest="to_date", required=True,
                        help="End date YYYYMMDD")
    parser.add_argument("--gender", default="both", choices=["M", "W", "both"],
                        help="Gender to backfill (default: both)")
    args = parser.parse_args()

    genders = ["M", "W"] if args.gender == "both" else [args.gender]
    dates = list(date_range(args.from_date, args.to_date))
    print(f"Backfilling {len(dates)} days ({args.from_date} -> {args.to_date}) for {', '.join(genders)}")

    session = SessionLocal()
    try:
        total_new = 0
        total_skipped = 0
        total_unmapped = 0

        for gender in genders:
            gender_label = "Men's" if gender == "M" else "Women's"
            gender_new = 0

            for date_str in dates:
                result = update_elo_from_espn(session, date_str, gender)

                if result["games_processed"] > 0:
                    print(f"  [{gender_label}] {date_str}: +{result['games_processed']} games "
                          f"({result['skipped']} skipped, {result['unmapped']} unmapped)")
                    for ch in result["changes"]:
                        print(f"    {ch['game']}")

                gender_new += result["games_processed"]
                total_skipped += result["skipped"]
                total_unmapped += result["unmapped"]

            total_new += gender_new

            if gender_new > 0:
                # Recompute W/L records from game_results (avoids double-counting)
                print(f"\n  [{gender_label}] Recomputing W/L records...")
                records_fixed = recompute_records(session, gender)
                print(f"  [{gender_label}] {records_fixed} team records corrected")

                print(f"  [{gender_label}] Refreshing conference strength...")
                conf_updated = refresh_conference_strength(session, gender)
                print(f"  [{gender_label}] {conf_updated} conferences updated")

                print(f"  [{gender_label}] Refreshing SOS...")
                sos_updated = refresh_sos(session, gender)
                print(f"  [{gender_label}] {sos_updated} teams SOS updated")
                session.commit()

            print(f"\n  [{gender_label}] Total new games: {gender_new}")

        print("\n=== Summary ===")
        print(f"  New games added: {total_new}")
        print(f"  Skipped (duplicates/invalid): {total_skipped}")
        print(f"  Unmapped (no Kaggle ID): {total_unmapped}")
        print("Done!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
