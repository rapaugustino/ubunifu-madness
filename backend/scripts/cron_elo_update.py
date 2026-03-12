"""
Daily update cron job — Elo ratings, player stats, and prediction locking.

Processes yesterday's and today's completed games for both Men's and Women's.
Designed to run once daily (e.g., 6 AM via cron or Railway scheduled service).

Pipeline:
1. Elo updates from ESPN game results
2. Conference strength refresh
3. Player box score ingestion
4. Season stats recomputation + importance scoring
5. SOS refresh
6. Advanced stats (adjusted efficiency, luck, etc.)
7. Record reconciliation from ESPN
8. Lock today's predictions (consistent pre-game state)

Run from backend/:
    python3 -m scripts.cron_elo_update

Cron example (6 AM daily):
    0 6 * * * cd /path/to/backend && python3 -m scripts.cron_elo_update >> /var/log/daily_update.log 2>&1
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from scripts.update_elo_live import update_elo_from_espn, refresh_conference_strength
from app.services.advanced_stats import compute_advanced_stats
from app.services.player_sync import (
    ingest_date_box_scores,
    recompute_season_stats,
    compute_importance_scores,
)
from app.models import PlayerSeasonStats, GameResult, EloRating, TeamSeasonStats, Team, GamePrediction
from app.services import espn
from app.services.predictor import predict_matchup


SEASON = 2026


def lock_todays_predictions(session, gender: str) -> int:
    """Pre-lock predictions for all of today's games so they use a consistent state.

    Fetches today's scoreboard from ESPN, maps teams to Kaggle IDs, and creates
    GamePrediction rows for any game that doesn't already have one.
    """
    today_str = datetime.now().strftime("%Y%m%d")
    games = espn.get_scoreboard(today_str, gender)

    espn_map = {
        t.espn_id: t
        for t in session.query(Team).filter(
            Team.espn_id.isnot(None), Team.gender == gender
        ).all()
    }

    locked_count = 0
    for game in games:
        espn_gid = str(game["id"])
        away_espn = game.get("away", {}).get("espnId")
        home_espn = game.get("home", {}).get("espnId")
        away_team = espn_map.get(away_espn)
        home_team = espn_map.get(home_espn)
        if not away_team or not home_team:
            continue

        # Skip if already locked
        existing = session.query(GamePrediction).filter(
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
        prob_away, source = predict_matchup(
            session, away_team.id, home_team.id, is_conf_tourney=is_conf_tourney
        )

        pred = GamePrediction(
            espn_game_id=espn_gid,
            game_date=today_str,
            season=SEASON,
            gender=gender,
            away_team_id=away_team.id,
            home_team_id=home_team.id,
            away_name=game["away"].get("name"),
            home_name=game["home"].get("name"),
            locked_prob_away=prob_away,
            prediction_source=source,
            game_type=detected_type,
        )
        session.add(pred)
        locked_count += 1

    session.flush()
    return locked_count


def reconcile_records(session, gender: str) -> int:
    """Sync win/loss records from ESPN for teams that have an espn_id.

    This catches conference tournament games or any games that the
    game-by-game Elo pipeline might have missed.
    """
    import time as _time

    teams = (
        session.query(Team, TeamSeasonStats)
        .join(TeamSeasonStats, (TeamSeasonStats.team_id == Team.id) & (TeamSeasonStats.season == SEASON))
        .filter(Team.gender == gender, Team.espn_id.isnot(None))
        .all()
    )

    corrected = 0
    for team, stats in teams:
        rec = espn.get_team_record(team.espn_id, gender)
        if not rec:
            continue
        espn_w, espn_l = rec["wins"], rec["losses"]
        if espn_w != stats.wins or espn_l != stats.losses:
            stats.wins = espn_w
            stats.losses = espn_l
            total = espn_w + espn_l
            stats.win_pct = round(espn_w / total, 4) if total > 0 else 0
            corrected += 1
        _time.sleep(0.05)  # be polite to ESPN API

    session.flush()
    return corrected


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
        w_id, l_id = g.w_team_id, g.l_team_id
        if w_id not in opponents:
            opponents[w_id] = []
        if l_id not in opponents:
            opponents[l_id] = []
        opponents[w_id].append(elo_map.get(l_id, 1500.0))
        opponents[l_id].append(elo_map.get(w_id, 1500.0))

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
                        loser = ch["loser"]
                        print(f"  {ch['game']}: {w['name']} {w['elo_before']:.1f}→{w['elo_after']:.1f}, "
                              f"{loser['name']} {loser['elo_before']:.1f}→{loser['elo_after']:.1f}")

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

            # --- Stage 5: Advanced stats (adjusted efficiency, luck, etc.) ---
            try:
                adv_count = compute_advanced_stats(session, SEASON, gender)
                session.commit()
                if adv_count > 0:
                    print(f"[{gender_label}] Advanced stats for {adv_count} teams")
            except Exception as e:
                session.rollback()
                print(f"[{gender_label}] Advanced stats error: {e}")

            # --- Stage 6: Reconcile records from ESPN ---
            try:
                rec_count = reconcile_records(session, gender)
                session.commit()
                if rec_count > 0:
                    print(f"[{gender_label}] Reconciled records for {rec_count} teams")
            except Exception as e:
                session.rollback()
                print(f"[{gender_label}] Record reconciliation error: {e}")

            # --- Stage 7: Lock today's predictions ---
            try:
                locked_count = lock_todays_predictions(session, gender)
                session.commit()
                if locked_count > 0:
                    print(f"[{gender_label}] Locked predictions for {locked_count} games")
                else:
                    print(f"[{gender_label}] All predictions already locked")
            except Exception as e:
                session.rollback()
                print(f"[{gender_label}] Prediction locking error: {e}")

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
