"""Backtest Kaggle submission CSVs against actual tournament results.

Compares predicted probabilities from submission files against real NCAA
tournament outcomes. Computes Brier score, log-loss, accuracy, calibration,
and per-season breakdowns. Supports comparing multiple submission versions
side-by-side.

Usage:
    cd backend
    # Backtest all Stage 1 submissions
    python3 -m scripts.backtest_submissions

    # Backtest specific file
    python3 -m scripts.backtest_submissions --file ../notebooks/submissions/stage1_submission_v5.csv

    # Backtest Stage 2 against conf tourney games in DB (stress test)
    python3 -m scripts.backtest_submissions --stage2
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
SUBMISSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "notebooks" / "submissions"

# Stage 1 covers seasons 2022-2025 (Kaggle scoring window)
STAGE1_SEASONS = [2022, 2023, 2024, 2025]


def load_tournament_results() -> pd.DataFrame:
    """Load actual NCAA tournament results from Kaggle CSVs."""
    frames = []
    for prefix, gender in [("M", "M"), ("W", "W")]:
        path = DATA_DIR / f"{prefix}NCAATourneyCompactResults.csv"
        if not path.exists():
            print(f"WARNING: {path} not found, skipping {gender}")
            continue
        df = pd.read_csv(path)
        df["gender"] = gender
        # Build the submission ID format: SEASON_LOWERID_HIGHERID
        df["lo"] = df[["WTeamID", "LTeamID"]].min(axis=1)
        df["hi"] = df[["WTeamID", "LTeamID"]].max(axis=1)
        df["ID"] = df["Season"].astype(str) + "_" + df["lo"].astype(str) + "_" + df["hi"].astype(str)
        # Did the lower-ID team win?
        df["lo_won"] = (df["WTeamID"] == df["lo"]).astype(int)
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def load_submission(path: Path) -> pd.DataFrame:
    """Load a submission CSV."""
    df = pd.read_csv(path)
    df.columns = ["ID", "Pred"]
    return df


def compute_metrics(preds: np.ndarray, actuals: np.ndarray) -> dict:
    """Compute Brier, log-loss, accuracy, and calibration metrics."""
    n = len(preds)
    if n == 0:
        return {}

    # Brier score
    brier = np.mean((preds - actuals) ** 2)

    # Log-loss (Kaggle's actual metric)
    eps = 1e-15
    preds_clipped = np.clip(preds, eps, 1 - eps)
    logloss = -np.mean(actuals * np.log(preds_clipped) + (1 - actuals) * np.log(1 - preds_clipped))

    # Accuracy
    pred_wins = (preds > 0.5).astype(int)
    accuracy = np.mean(pred_wins == actuals)

    # Confident accuracy (>= 55%)
    confident_mask = np.maximum(preds, 1 - preds) >= 0.55
    conf_acc = np.mean(pred_wins[confident_mask] == actuals[confident_mask]) if confident_mask.sum() > 0 else None
    tossups = int((~confident_mask).sum())

    # Calibration: bin by predicted confidence, compare to actual
    confidence = np.maximum(preds, 1 - preds)
    bins = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70),
            (0.70, 0.75), (0.75, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 1.0)]
    calibration = []
    for lo, hi in bins:
        mask = (confidence >= lo) & (confidence < hi)
        if mask.sum() > 0:
            # For calibration: favored team win rate
            favored_won = np.where(preds > 0.5, actuals, 1 - actuals)
            cal_pred = confidence[mask].mean()
            cal_actual = favored_won[mask].mean()
            calibration.append({
                "band": f"{lo:.0%}-{hi:.0%}",
                "predicted": cal_pred,
                "actual": cal_actual,
                "gap": cal_actual - cal_pred,
                "games": int(mask.sum()),
            })

    return {
        "n": n,
        "brier": brier,
        "logloss": logloss,
        "accuracy": accuracy,
        "conf_accuracy": conf_acc,
        "tossups": tossups,
        "calibration": calibration,
    }


def backtest_submission(sub_path: Path, results: pd.DataFrame, seasons: list[int] | None = None) -> dict:
    """Backtest a single submission file against tournament results."""
    sub = load_submission(sub_path)

    # Filter results to requested seasons
    if seasons:
        results = results[results["Season"].isin(seasons)]

    # Merge: inner join on ID
    merged = results.merge(sub, on="ID", how="inner")

    if len(merged) == 0:
        return {"error": "No matching games found"}

    preds = merged["Pred"].values
    actuals = merged["lo_won"].values

    overall = compute_metrics(preds, actuals)

    # Per-season breakdown
    per_season = {}
    for season in sorted(merged["Season"].unique()):
        mask = merged["Season"] == season
        per_season[season] = compute_metrics(preds[mask], actuals[mask])

    # Per-gender breakdown
    per_gender = {}
    for gender in sorted(merged["gender"].unique()):
        mask = merged["gender"] == gender
        per_gender[gender] = compute_metrics(preds[mask], actuals[mask])

    return {
        "file": sub_path.name,
        "matched_games": len(merged),
        "total_in_submission": len(sub),
        "overall": overall,
        "per_season": per_season,
        "per_gender": per_gender,
    }


def print_results(result: dict):
    """Pretty-print backtest results."""
    print(f"\n{'='*80}")
    print(f"  {result['file']}")
    print(f"  Matched {result['matched_games']} tournament games")
    print(f"{'='*80}")

    m = result["overall"]
    print(f"\n  OVERALL:")
    print(f"    Brier:      {m['brier']:.4f}")
    print(f"    Log-Loss:   {m['logloss']:.4f}  (Kaggle metric)")
    print(f"    Accuracy:   {m['accuracy']:.1%}")
    if m["conf_accuracy"] is not None:
        print(f"    Conf Acc:   {m['conf_accuracy']:.1%}  ({m['n'] - m['tossups']} confident, {m['tossups']} tossups)")

    # Per-gender
    if result.get("per_gender"):
        print(f"\n  BY GENDER:")
        for g, gm in result["per_gender"].items():
            label = "Men" if g == "M" else "Women"
            print(f"    {label:6s}: Brier {gm['brier']:.4f}  LogLoss {gm['logloss']:.4f}  Acc {gm['accuracy']:.1%}  ({gm['n']} games)")

    # Per-season
    if result.get("per_season"):
        print(f"\n  BY SEASON:")
        for s, sm in result["per_season"].items():
            print(f"    {s}: Brier {sm['brier']:.4f}  LogLoss {sm['logloss']:.4f}  Acc {sm['accuracy']:.1%}  ({sm['n']} games)")

    # Calibration
    cal = m.get("calibration", [])
    if cal:
        print(f"\n  CALIBRATION:")
        print(f"    {'Band':<10} {'Pred':>6} {'Actual':>7} {'Gap':>7} {'Games':>6}")
        for c in cal:
            gap_str = f"{c['gap']:+.1%}"
            color = "" if abs(c["gap"]) < 0.05 else " !"
            print(f"    {c['band']:<10} {c['predicted']:>5.1%}  {c['actual']:>6.1%}  {gap_str:>7} {c['games']:>5}{color}")


def backtest_stage2_vs_db():
    """Stress-test Stage 2 submissions against live GamePrediction results."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.database import SessionLocal
    from app.models import GamePrediction

    db = SessionLocal()
    preds = db.query(GamePrediction).filter(
        GamePrediction.season == 2026,
        GamePrediction.model_correct.isnot(None)
    ).all()
    db.close()

    if not preds:
        print("No resolved 2026 predictions in DB.")
        return

    # Build a lookup: ID -> actual outcome
    actuals_map = {}
    for p in preds:
        lo = min(p.away_team_id, p.home_team_id)
        hi = max(p.away_team_id, p.home_team_id)
        game_id = f"2026_{lo}_{hi}"
        lo_won = 1 if p.winner_team_id == lo else 0
        actuals_map[game_id] = lo_won

    print(f"\n{len(actuals_map)} resolved 2026 games in DB")

    # Test each Stage 2 submission
    stage2_files = sorted(SUBMISSIONS_DIR.glob("stage2_submission*.csv"))
    for sub_path in stage2_files:
        sub = load_submission(sub_path)
        matched_preds = []
        matched_actuals = []
        for _, row in sub.iterrows():
            if row["ID"] in actuals_map:
                matched_preds.append(row["Pred"])
                matched_actuals.append(actuals_map[row["ID"]])

        if not matched_preds:
            print(f"\n  {sub_path.name}: 0 matches")
            continue

        preds_arr = np.array(matched_preds)
        actuals_arr = np.array(matched_actuals)
        m = compute_metrics(preds_arr, actuals_arr)

        print(f"\n  {sub_path.name}: {m['n']} games matched")
        print(f"    Brier: {m['brier']:.4f}  LogLoss: {m['logloss']:.4f}  Accuracy: {m['accuracy']:.1%}")


def main():
    parser = argparse.ArgumentParser(description="Backtest Kaggle submissions against tournament results")
    parser.add_argument("--file", type=str, help="Backtest a specific submission file")
    parser.add_argument("--stage2", action="store_true", help="Stress-test Stage 2 against DB game results")
    parser.add_argument("--seasons", type=str, default=None, help="Comma-separated seasons (e.g., 2023,2024)")
    args = parser.parse_args()

    if args.stage2:
        backtest_stage2_vs_db()
        return

    results = load_tournament_results()
    total_games = len(results)
    seasons_available = sorted(results["Season"].unique())
    print(f"Loaded {total_games} tournament games ({seasons_available[0]}-{seasons_available[-1]})")
    print(f"Stage 1 scoring window: {STAGE1_SEASONS}")

    seasons = [int(s) for s in args.seasons.split(",")] if args.seasons else STAGE1_SEASONS

    if args.file:
        # Single file
        path = Path(args.file)
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)
        result = backtest_submission(path, results, seasons)
        print_results(result)
    else:
        # All Stage 1 submissions
        stage1_files = sorted(SUBMISSIONS_DIR.glob("stage1_submission*.csv"))
        if not stage1_files:
            print("No Stage 1 submissions found in notebooks/submissions/")
            sys.exit(1)

        # Comparison table
        all_results = []
        for sub_path in stage1_files:
            result = backtest_submission(sub_path, results, seasons)
            all_results.append(result)
            print_results(result)

        # Side-by-side comparison
        if len(all_results) > 1:
            print(f"\n{'='*80}")
            print("  COMPARISON (Stage 1 - all versions)")
            print(f"{'='*80}")
            print(f"  {'Version':<35} {'Brier':>7} {'LogLoss':>8} {'Acc':>6} {'Games':>6}")
            print(f"  {'-'*70}")
            for r in all_results:
                m = r["overall"]
                print(f"  {r['file']:<35} {m['brier']:>7.4f} {m['logloss']:>8.4f} {m['accuracy']:>5.1%} {m['n']:>5}")


if __name__ == "__main__":
    main()
