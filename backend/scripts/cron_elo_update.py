"""
Daily update cron job — Elo ratings, player stats, and prediction locking.

Processes yesterday's and today's completed games for both Men's and Women's.
Designed to run once daily (e.g., 6 AM via cron or Railway scheduled service).

Pipeline:
1. Elo updates from ESPN game results
2. Conference strength refresh
3. Player box score ingestion
4. Season stats recomputation + importance scoring
5. Prediction locking for upcoming games (via scores endpoint on next access)

Run from backend/:
    python -m scripts.cron_elo_update

Cron example (6 AM daily):
    0 6 * * * cd /path/to/backend && python -m scripts.cron_elo_update >> /var/log/daily_update.log 2>&1
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from scripts.update_elo_live import update_elo_from_espn, refresh_conference_strength
from app.services.player_sync import (
    ingest_date_box_scores,
    recompute_season_stats,
    compute_importance_scores,
)
from app.models import PlayerSeasonStats, GameResult, EloRating, TeamSeasonStats


SEASON = 2026


def refresh_sos(session, gender: str) -> int:
    """Recompute SOS (avg opponent Elo) for all teams from game results."""
    elo_map = {
        r.team_id: r.elo
        for r in session.query(EloRating).filter(EloRating.season == SEASON).all()
    }
    games = session.query(GameResult).filter(
        GameResult.season == SEASON, GameResult.gender == gender
    ).all()

    opponents: dict[int, list[float]] = {}
    for g in games:
        w, l = g.w_team_id, g.l_team_id
        if w not in opponents:
            opponents[w] = []
        if l not in opponents:
            opponents[l] = []
        opponents[w].append(elo_map.get(l, 1500.0))
        opponents[l].append(elo_map.get(w, 1500.0))

    updated = 0
    for tid, opp_elos in opponents.items():
        if opp_elos:
            sos = sum(opp_elos) / len(opp_elos)
            stats = session.query(TeamSeasonStats).filter(
                TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == tid
            ).first()
            if stats:
                stats.sos = round(sos, 1)
                updated += 1

    session.flush()
    return updated


def run():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    dates = [yesterday.strftime("%Y%m%d"), today.strftime("%Y%m%d")]

    print(f"=== Daily Update: {today.strftime('%Y-%m-%d %H:%M')} ===")

    session = SessionLocal()
    try:
        for gender in ["M", "W"]:
            gender_label = "Men's" if gender == "M" else "Women's"

            # --- Stage 1: Elo updates ---
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

            # --- Stage 2: Player box score ingestion ---
            for date_str in dates:
                try:
                    ingest_result = ingest_date_box_scores(session, date_str, gender)
                    if ingest_result["games_processed"] > 0:
                        print(f"[{gender_label}] {date_str}: {ingest_result['player_logs_created']} player logs from {ingest_result['games_processed']} games")
                except Exception as e:
                    print(f"[{gender_label}] Player ingestion error for {date_str}: {e}")

            # --- Stage 3: Recompute season stats ---
            try:
                stats_count = recompute_season_stats(session, gender=gender)
                session.commit()
                if stats_count > 0:
                    print(f"[{gender_label}] Recomputed stats for {stats_count} players")

                    # Compute importance scores for all teams with player data
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
                    if importance_count > 0:
                        print(f"[{gender_label}] Computed importance for {importance_count} players")
            except Exception as e:
                session.rollback()
                print(f"[{gender_label}] Stats recompute error: {e}")

            # --- Stage 4: Refresh SOS (strength of schedule) ---
            try:
                sos_count = refresh_sos(session, gender)
                session.commit()
                if sos_count > 0:
                    print(f"[{gender_label}] Updated SOS for {sos_count} teams")
            except Exception as e:
                session.rollback()
                print(f"[{gender_label}] SOS error: {e}")

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
