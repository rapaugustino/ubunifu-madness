"""
Update Elo ratings from ESPN live game results.

Fetches completed games from ESPN, applies Elo updates for any new games,
and refreshes conference strength metrics.

Run from backend/:
    python -m scripts.update_elo_live [--date YYYYMMDD] [--gender M|W]
"""

import argparse
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Team, EloRating, GameResult, TeamSeasonStats,
    TeamConference, ConferenceStrength,
)
from app.services import espn

# Elo config — must match compute_stats.py exactly
K_FACTOR = 21.8
HOME_ADV = 101.9
MEAN_ELO = 1500
SEASON = 2026


def expected_win_prob(elo_a: float, elo_b: float) -> float:
    """Standard Elo expected win probability."""
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def elo_update(winner_elo: float, loser_elo: float, mov: int, w_loc: str) -> float:
    """Compute Elo rating change for one game. Returns the update amount."""
    elo_w = winner_elo + (HOME_ADV if w_loc == "H" else 0)
    elo_l = loser_elo + (HOME_ADV if w_loc == "A" else 0)

    exp_w = expected_win_prob(elo_w, elo_l)
    mult = math.log(abs(mov) + 1) * (2.2 / ((abs(elo_w - elo_l) * 0.001) + 2.2))
    return K_FACTOR * mult * (1 - exp_w)


def _game_already_exists(session: Session, season: int, w_id: int, l_id: int, w_score: int, l_score: int) -> bool:
    """Check if a game result is already stored (deduplication)."""
    return session.query(GameResult).filter(
        GameResult.season == season,
        GameResult.w_team_id == w_id,
        GameResult.l_team_id == l_id,
        GameResult.w_score == w_score,
        GameResult.l_score == l_score,
    ).first() is not None


def _get_espn_to_kaggle_map(session: Session, gender: str) -> dict[int, Team]:
    """Build ESPN ID → Team mapping."""
    return {
        t.espn_id: t
        for t in session.query(Team).filter(
            Team.espn_id.isnot(None),
            Team.gender == gender,
        ).all()
    }


def _load_current_elo(session: Session) -> dict[int, float]:
    """Load current Elo ratings for all teams in the target season."""
    return {
        r.team_id: r.elo
        for r in session.query(EloRating).filter(EloRating.season == SEASON).all()
    }


def update_elo_from_espn(session: Session, date_str: str, gender: str) -> dict:
    """
    Fetch completed games from ESPN for a given date and update Elo ratings.

    Returns summary dict with games_processed, skipped, changes list.
    """
    espn_map = _get_espn_to_kaggle_map(session, gender)
    elo = _load_current_elo(session)

    games = espn.get_scoreboard(date_str, gender)
    final_games = [g for g in games if g["status"] == "STATUS_FINAL"]

    processed = 0
    skipped = 0
    unmapped = 0
    changes = []

    for game in final_games:
        away = game.get("away", {})
        home = game.get("home", {})

        # Map to Kaggle teams
        away_team = espn_map.get(away.get("espnId"))
        home_team = espn_map.get(home.get("espnId"))

        if not away_team or not home_team:
            unmapped += 1
            continue

        away_score = away.get("score", 0)
        home_score = home.get("score", 0)

        if away_score == home_score or away_score == 0 or home_score == 0:
            skipped += 1
            continue

        # Determine winner/loser
        if home_score > away_score:
            w_team, l_team = home_team, away_team
            w_score, l_score = home_score, away_score
            w_loc = "H"
        else:
            w_team, l_team = away_team, home_team
            w_score, l_score = away_score, home_score
            w_loc = "A"

        # Deduplication check
        if _game_already_exists(session, SEASON, w_team.id, l_team.id, w_score, l_score):
            skipped += 1
            continue

        # Get current Elo (or default)
        w_elo = elo.get(w_team.id, MEAN_ELO)
        l_elo = elo.get(l_team.id, MEAN_ELO)

        # Compute update
        mov = w_score - l_score
        update = elo_update(w_elo, l_elo, mov, w_loc)

        new_w_elo = round(w_elo + update, 1)
        new_l_elo = round(l_elo - update, 1)

        # Store game result
        # Approximate day_num from date (days since Nov 1)
        try:
            game_date = datetime.strptime(date_str, "%Y%m%d")
            season_start = datetime(game_date.year if game_date.month >= 11 else game_date.year - 1, 11, 1)
            day_num = (game_date - season_start).days
        except ValueError:
            day_num = 130  # fallback

        session.add(GameResult(
            season=SEASON,
            day_num=day_num,
            w_team_id=w_team.id,
            w_score=w_score,
            l_team_id=l_team.id,
            l_score=l_score,
            w_loc=w_loc,
            num_ot=0,
            game_type="regular",
            gender=gender,
        ))

        # Update Elo in DB
        for team_id, new_elo_val in [(w_team.id, new_w_elo), (l_team.id, new_l_elo)]:
            elo_row = session.query(EloRating).filter(
                EloRating.season == SEASON,
                EloRating.team_id == team_id,
                EloRating.snapshot_day == 154,
            ).first()
            if elo_row:
                elo_row.elo = new_elo_val
            else:
                session.add(EloRating(
                    season=SEASON, team_id=team_id,
                    elo=new_elo_val, snapshot_day=154,
                ))

        # Update in-memory elo for subsequent games this batch
        elo[w_team.id] = new_w_elo
        elo[l_team.id] = new_l_elo

        # Update team season stats (wins/losses)
        for team_id, is_winner in [(w_team.id, True), (l_team.id, False)]:
            stats = session.query(TeamSeasonStats).filter(
                TeamSeasonStats.season == SEASON,
                TeamSeasonStats.team_id == team_id,
            ).first()
            if stats:
                if is_winner:
                    stats.wins = (stats.wins or 0) + 1
                else:
                    stats.losses = (stats.losses or 0) + 1
                total = (stats.wins or 0) + (stats.losses or 0)
                stats.win_pct = round(stats.wins / total, 4) if total > 0 else 0

        changes.append({
            "game": f"{w_team.name} {w_score} - {l_team.name} {l_score}",
            "winner": {"name": w_team.name, "elo_before": w_elo, "elo_after": new_w_elo},
            "loser": {"name": l_team.name, "elo_before": l_elo, "elo_after": new_l_elo},
            "update": round(update, 1),
        })
        processed += 1

    session.commit()

    return {
        "date": date_str,
        "gender": gender,
        "games_found": len(final_games),
        "games_processed": processed,
        "skipped": skipped,
        "unmapped": unmapped,
        "changes": changes,
    }


def refresh_conference_strength(session: Session, gender: str):
    """Recompute conference strength metrics from current Elo ratings."""
    import numpy as np

    elo_map = _load_current_elo(session)

    # Load team → conference mapping
    tc_rows = session.query(TeamConference).filter(TeamConference.season == SEASON).all()
    conf_teams: dict[str, list[int]] = {}
    for tc in tc_rows:
        g = "M" if tc.team_id < 2000 else "W"
        if g != gender:
            continue
        conf_teams.setdefault(tc.conf_abbrev, []).append(tc.team_id)

    updated = 0
    for conf, team_ids in conf_teams.items():
        elos = [elo_map.get(tid, MEAN_ELO) for tid in team_ids]
        if not elos:
            continue

        avg_elo = float(np.mean(elos))
        elo_depth = float(np.std(elos)) if len(elos) > 1 else 0.0
        top5_elo = float(np.mean(sorted(elos, reverse=True)[:5]))

        cs = session.query(ConferenceStrength).filter(
            ConferenceStrength.season == SEASON,
            ConferenceStrength.gender == gender,
            ConferenceStrength.conf_abbrev == conf,
        ).first()
        if cs:
            cs.avg_elo = round(avg_elo, 2)
            cs.elo_depth = round(elo_depth, 2)
            cs.top5_elo = round(top5_elo, 2)
            updated += 1

    session.commit()
    return updated


def main():
    parser = argparse.ArgumentParser(description="Update Elo ratings from ESPN game results")
    parser.add_argument("--date", help="Date in YYYYMMDD format (default: today)")
    parser.add_argument("--gender", default="M", choices=["M", "W"], help="Gender (default: M)")
    parser.add_argument("--yesterday", action="store_true", help="Also process yesterday's games")
    args = parser.parse_args()

    dates = []
    if args.date:
        dates.append(args.date)
    else:
        today = datetime.now()
        dates.append(today.strftime("%Y%m%d"))
        if args.yesterday:
            dates.append((today - timedelta(days=1)).strftime("%Y%m%d"))

    session = SessionLocal()
    try:
        total_processed = 0
        for date_str in dates:
            print(f"\n--- Processing {args.gender} games for {date_str} ---")
            result = update_elo_from_espn(session, date_str, args.gender)

            print(f"  Found: {result['games_found']} final games")
            print(f"  Processed: {result['games_processed']} new games")
            print(f"  Skipped: {result['skipped']} (already in DB or invalid)")
            print(f"  Unmapped: {result['unmapped']} (no Kaggle team ID)")

            for ch in result["changes"]:
                w = ch["winner"]
                l = ch["loser"]
                print(f"  {ch['game']}: {w['name']} {w['elo_before']:.1f}→{w['elo_after']:.1f} (+{ch['update']}), "
                      f"{l['name']} {l['elo_before']:.1f}→{l['elo_after']:.1f} (-{ch['update']})")

            total_processed += result["games_processed"]

        # Refresh conference strength if any games were processed
        if total_processed > 0:
            print(f"\nRefreshing conference strength for {args.gender}...")
            conf_updated = refresh_conference_strength(session, args.gender)
            print(f"  {conf_updated} conferences updated")

        print("\nDone!")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
