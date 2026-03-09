"""
Daily Elo update cron job.

Processes yesterday's and today's completed games for both Men's and Women's.
Designed to run once daily (e.g., 6 AM via cron or Railway scheduled service).

Run from backend/:
    python -m scripts.cron_elo_update

Cron example (6 AM daily):
    0 6 * * * cd /path/to/backend && python -m scripts.cron_elo_update >> /var/log/elo_update.log 2>&1
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from scripts.update_elo_live import update_elo_from_espn, refresh_conference_strength


def run():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    dates = [yesterday.strftime("%Y%m%d"), today.strftime("%Y%m%d")]

    print(f"=== Elo Update: {today.strftime('%Y-%m-%d %H:%M')} ===")

    session = SessionLocal()
    try:
        for gender in ["M", "W"]:
            gender_label = "Men's" if gender == "M" else "Women's"
            total_processed = 0

            for date_str in dates:
                result = update_elo_from_espn(session, date_str, gender)
                total_processed += result["games_processed"]

                if result["games_processed"] > 0:
                    print(f"\n[{gender_label}] {date_str}: {result['games_processed']} games processed")
                    for ch in result["changes"]:
                        w = ch["winner"]
                        l = ch["loser"]
                        print(f"  {ch['game']}: {w['name']} {w['elo_before']:.1f}→{w['elo_after']:.1f}, "
                              f"{l['name']} {l['elo_before']:.1f}→{l['elo_after']:.1f}")

            if total_processed > 0:
                conf_updated = refresh_conference_strength(session, gender)
                print(f"[{gender_label}] {conf_updated} conferences refreshed")
            else:
                print(f"[{gender_label}] No new games to process")

        print("\n=== Done ===")
    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    run()
