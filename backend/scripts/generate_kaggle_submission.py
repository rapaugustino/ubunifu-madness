"""
Generate a Kaggle Stage 2 submission from live app predictions.

Generate a Kaggle Stage 2 submission from the live V6 ML ensemble.

Pulls probabilities from the same model that powers the app for all
possible 2026 tournament matchups. For matchups already predicted and
locked in GamePrediction, uses those locked values for consistency.
For all others, computes fresh predictions.

When to run: before each Kaggle submission deadline (Stage 1 and Stage 2),
after model artifacts have been uploaded and daily cron has run.

Usage:
    cd backend
    python3 -m scripts.generate_kaggle_submission -o ../notebooks/submissions/stage2_submission.csv
"""

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Team, EloRating, GamePrediction
from app.services.predictor import predict_matchup, load_model_bundle, reload_model_bundle

SEASON = 2026
SUBMISSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "notebooks" / "submissions"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"


def load_sample_submission() -> pd.DataFrame:
    """Load the Kaggle sample submission to get the required ID format."""
    # Try Stage 2 sample first
    for name in ["SampleSubmissionStage2.csv", "SampleSubmission2025.csv"]:
        path = DATA_DIR / name
        if path.exists():
            df = pd.read_csv(path)
            # Filter to 2026 only
            df = df[df["ID"].str.startswith("2026_")]
            if len(df) > 0:
                return df

    # If no sample file, generate all possible pairings
    return None


def get_all_team_ids(db, gender: str) -> list[int]:
    """Get all team IDs that have Elo ratings for the current season."""
    rows = (
        db.query(EloRating.team_id)
        .join(Team, Team.id == EloRating.team_id)
        .filter(EloRating.season == SEASON, Team.gender == gender)
        .all()
    )
    return sorted(r.team_id for r in rows)


def generate_all_pairings(team_ids: list[int]) -> list[tuple[int, int]]:
    """Generate all (lo, hi) pairings for submission."""
    pairings = []
    for i, a in enumerate(team_ids):
        for b in team_ids[i + 1:]:
            pairings.append((a, b))
    return pairings


def main():
    parser = argparse.ArgumentParser(
        description="Generate Kaggle Stage 2 submission from live app predictions"
    )
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output CSV path (default: stage2_live_v5.csv in submissions/)")
    parser.add_argument("--calibrate", action="store_true",
                        help="Run calibrate_submission.py on the output after generation")
    parser.add_argument("--clip-min", type=float, default=0.05,
                        help="Min probability for clipping (default: 0.05)")
    parser.add_argument("--clip-max", type=float, default=0.95,
                        help="Max probability for clipping (default: 0.95)")
    parser.add_argument("--gender", type=str, default=None,
                        help="Generate for one gender only (M or W)")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else SUBMISSIONS_DIR / "stage2_submission.csv"

    db = SessionLocal()
    reload_model_bundle()
    bundle = load_model_bundle(db)

    if bundle:
        print(f"Model loaded: {len(bundle.feature_cols)} features, "
              f"weights LR={bundle.weights.get('lr', '?')}, LGB={bundle.weights.get('lgb', '?')}")
    else:
        print("WARNING: No ML model artifacts found. Will use Elo+Record fallback.")

    # Load locked predictions from GamePrediction table
    locked = {}
    gp_rows = db.query(GamePrediction).filter(GamePrediction.season == SEASON).all()
    for gp in gp_rows:
        lo = min(gp.away_team_id, gp.home_team_id)
        hi = max(gp.away_team_id, gp.home_team_id)
        # Store as P(lo_id wins)
        if gp.away_team_id == lo:
            locked[(lo, hi)] = gp.locked_prob_away
        else:
            locked[(lo, hi)] = 1.0 - gp.locked_prob_away
    print(f"Loaded {len(locked)} locked predictions from GamePrediction table")

    # Check for sample submission
    sample = load_sample_submission()

    genders = [args.gender] if args.gender else ["M", "W"]
    rows = []

    for gender in genders:
        team_ids = get_all_team_ids(db, gender)
        print(f"\n{gender}: {len(team_ids)} teams")

        if sample is not None:
            # Use sample submission IDs for this gender
            gender_ids = set(team_ids)
            pairings = []
            for _, row in sample.iterrows():
                parts = row["ID"].split("_")
                a, b = int(parts[1]), int(parts[2])
                if a in gender_ids or b in gender_ids:
                    pairings.append((a, b))
            print(f"  {len(pairings)} pairings from sample submission")
        else:
            pairings = generate_all_pairings(team_ids)
            print(f"  {len(pairings)} pairings generated")

        used_locked = 0
        computed = 0

        total_pairings = len(pairings)
        for idx, (lo, hi) in enumerate(pairings):
            game_id = f"2026_{lo}_{hi}"

            # Use locked prediction if available
            if (lo, hi) in locked:
                prob = locked[(lo, hi)]
                used_locked += 1
            else:
                try:
                    prob_a, _ = predict_matchup(db, lo, hi, is_neutral=True)
                    prob = prob_a
                except Exception:
                    prob = 0.5
                computed += 1

            prob = np.clip(prob, args.clip_min, args.clip_max)
            rows.append({"ID": game_id, "Pred": prob})

            if (idx + 1) % 5000 == 0:
                print(f"  ... {idx + 1}/{total_pairings} ({(idx+1)/total_pairings:.0%})")

        print(f"  {used_locked} from locked predictions, {computed} freshly computed")

    db.close()

    # Build DataFrame and write
    df = pd.DataFrame(rows)
    df = df.sort_values("ID").reset_index(drop=True)
    df.to_csv(output_path, index=False)

    print(f"\nWritten {len(df)} predictions to {output_path.name}")
    print(f"  Range: [{df['Pred'].min():.4f}, {df['Pred'].max():.4f}]")
    print(f"  Mean: {df['Pred'].mean():.4f}")

    # Optionally run calibration
    if args.calibrate:
        print("\nRunning calibration...")
        from scripts.calibrate_submission import calibrate_submission
        calibrate_submission(output_path, clip_min=args.clip_min, clip_max=args.clip_max)


if __name__ == "__main__":
    main()
