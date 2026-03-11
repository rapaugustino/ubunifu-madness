"""Test V3 model predictions against past game results in the DB.

Usage:
    cd backend
    python3 -m scripts.test_v3_predictions
"""

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import GameResult, Team
from app.services.predictor import predict_matchup, load_model_bundle

TOSSUP_THRESHOLD = 0.55


def main():
    db = SessionLocal()

    # 1. Verify V3 artifacts are loaded
    bundle = load_model_bundle(db)
    if bundle:
        print(f"V3 artifacts loaded: {len(bundle.feature_cols)} features, weights={bundle.weights}")
    else:
        print("WARNING: No ML artifacts in DB — predictions will use blended/live_blend fallback")

    # 2. Load recent completed games from 2026 season (limit for speed)
    MAX_GAMES = 200
    games = (
        db.query(GameResult)
        .filter(GameResult.season == 2026)
        .order_by(GameResult.day_num.desc())
        .limit(MAX_GAMES)
        .all()
    )

    if not games:
        print("No 2026 games found in DB.")
        db.close()
        return

    print(f"\nTesting against {len(games)} games from 2026 season")
    print(f"Tossup threshold: {TOSSUP_THRESHOLD}")
    print(f"{'='*90}")
    print(f"{'Winner':<20} {'Loser':<20} {'Pred':>6} {'Source':<14} {'Conf':>5} {'Result':>8}")
    print(f"{'-'*90}")

    # Team name cache
    team_names = {}

    def get_name(tid):
        if tid not in team_names:
            t = db.query(Team).filter(Team.id == tid).first()
            team_names[tid] = t.name if t else str(tid)
        return team_names[tid]

    total = 0
    correct = 0
    confident_total = 0
    confident_correct = 0
    tossups = 0
    sources = {}
    misses = []

    for game in games:
        w_id = game.w_team_id
        l_id = game.l_team_id

        # Convention: lower ID = team_a
        lo, hi = min(w_id, l_id), max(w_id, l_id)

        try:
            prob_lo, source = predict_matchup(db, lo, hi)
        except Exception as e:
            print(f"  ERROR predicting {lo} vs {hi}: {e}")
            continue

        # prob_lo = P(lower_id wins)
        # Did lower_id actually win?
        lo_won = w_id == lo
        pred_lo_wins = prob_lo > 0.5

        confidence = max(prob_lo, 1 - prob_lo)
        is_tossup = confidence < TOSSUP_THRESHOLD
        is_correct = pred_lo_wins == lo_won

        total += 1
        sources[source] = sources.get(source, 0) + 1

        if is_tossup:
            tossups += 1
            result_str = "TOSSUP"
        else:
            confident_total += 1
            if is_correct:
                confident_correct += 1
                correct += 1
                result_str = "OK"
            else:
                correct += 0
                result_str = "MISS"
                misses.append({
                    "winner": get_name(w_id),
                    "loser": get_name(l_id),
                    "prob": prob_lo,
                    "confidence": confidence,
                    "source": source,
                })

        if not is_tossup:
            w_name = get_name(w_id)
            l_name = get_name(l_id)
            print(f"{w_name:<20} {l_name:<20} {prob_lo:>6.3f} {source:<14} {confidence:>4.1%} {result_str:>8}")

    # Summary
    print(f"\n{'='*90}")
    print(f"SUMMARY")
    print(f"{'='*90}")
    print(f"Total games:       {total}")
    print(f"Tossups (<{TOSSUP_THRESHOLD:.0%}):   {tossups}")
    print(f"Confident games:   {confident_total}")
    print(f"Confident correct: {confident_correct}")
    if confident_total > 0:
        print(f"Confident accuracy: {confident_correct/confident_total:.1%}")
    if total > 0:
        print(f"Overall accuracy:  {correct/total:.1%} (including tossups as wrong)")

    print(f"\nPrediction sources:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src:<14} {count:>4} games")

    if misses:
        print(f"\nBIGGEST MISSES (confident but wrong):")
        misses.sort(key=lambda m: -m["confidence"])
        for m in misses[:15]:
            print(f"  {m['confidence']:>5.1%} conf — {m['winner']} beat {m['loser']} ({m['source']})")

    db.close()


if __name__ == "__main__":
    main()
