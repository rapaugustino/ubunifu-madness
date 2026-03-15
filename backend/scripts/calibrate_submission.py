"""
Apply post-hoc calibration to a Kaggle submission CSV.

Reads a raw submission, applies probability corrections based on live
2026 performance data, and writes a calibrated version. Designed to
run right before submitting to Kaggle.

Three corrections applied in order:
  1. High-confidence compression (same as live app recalibration)
  2. Seed-based prior blending for NCAA tournament matchups
  3. Probability clipping to limit log-loss penalty from extreme values

Usage:
    cd backend

    # Default: clip only (conservative, safe for any submission)
    python3 -m scripts.calibrate_submission ../notebooks/submissions/stage2_submission_v5.csv

    # With compression + seed priors (experimental, may hurt well-calibrated models)
    python3 -m scripts.calibrate_submission --recal --seed-blend 0.10 INPUT.csv

    # Tighter clipping
    python3 -m scripts.calibrate_submission --clip-min 0.05 --clip-max 0.95 INPUT.csv

    # Preview without writing
    python3 -m scripts.calibrate_submission --dry-run INPUT.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
SUBMISSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "notebooks" / "submissions"

# Historical upset rates by seed matchup (1985-2025 NCAA tournament).
# Key: (high_seed, low_seed) -> P(high_seed_wins).
# High seed = worse seed number (e.g. 16 in a 1v16 matchup).
HISTORICAL_UPSET_RATES = {
    (16, 1): 0.010,
    (15, 2): 0.060,
    (14, 3): 0.150,
    (13, 4): 0.210,
    (12, 5): 0.355,
    (11, 6): 0.375,
    (10, 7): 0.390,
    (9, 8): 0.480,
}


def load_seeds(season: int) -> dict[int, int]:
    """Load tournament seeds for a given season. Returns {team_id: seed_number}."""
    seeds = {}
    for prefix in ["M", "W"]:
        path = DATA_DIR / f"{prefix}NCAATourneySeeds.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df = df[df["Season"] == season]
        for _, row in df.iterrows():
            # Seed format: "W01", "X16a" etc. Extract the number.
            seed_str = row["Seed"]
            seed_num = int("".join(c for c in seed_str if c.isdigit())[:2])
            seeds[row["TeamID"]] = seed_num
    return seeds


def get_seed_prior(seed_a: int, seed_b: int) -> float | None:
    """Get historical P(team_a wins) based on seed matchup.

    Returns None if the matchup doesn't have a clean historical prior
    (e.g. same seed, or matchup not in first-round lookup).
    """
    if seed_a == seed_b:
        return None

    # Determine which is the upset side
    high_seed = max(seed_a, seed_b)
    low_seed = min(seed_a, seed_b)

    upset_rate = HISTORICAL_UPSET_RATES.get((high_seed, low_seed))
    if upset_rate is None:
        # Not a standard first-round matchup. Use a seed-diff logistic.
        seed_diff = seed_b - seed_a  # positive = team_a is better seed
        # Rough logistic: each seed difference is worth ~5% probability
        prior = 1.0 / (1.0 + 10.0 ** (-seed_diff * 0.15))
        return prior

    # team_a is the low seed (better) -> P(a wins) = 1 - upset_rate
    if seed_a < seed_b:
        return 1.0 - upset_rate
    else:
        return upset_rate


def recalibrate_high_confidence(prob: float) -> float:
    """Compress predictions above 72% confidence toward 50%.

    Same function used in the live app (predictor.py). Based on
    2026 live calibration showing overconfidence at high levels.
    """
    THRESHOLD = 0.72
    COMPRESSION = 0.25

    confidence = abs(prob - 0.5)
    threshold_dist = THRESHOLD - 0.5

    if confidence <= threshold_dist:
        return prob

    excess = confidence - threshold_dist
    compressed_excess = excess * (1 - COMPRESSION)
    new_confidence = threshold_dist + compressed_excess

    if prob >= 0.5:
        return 0.5 + new_confidence
    else:
        return 0.5 - new_confidence


def calibrate_submission(
    input_path: Path,
    clip_min: float = 0.03,
    clip_max: float = 0.97,
    seed_blend: float = 0.0,
    apply_recal: bool = False,
    dry_run: bool = False,
) -> Path | None:
    """Apply calibration corrections to a submission CSV.

    Default settings are conservative (clip only). Backtesting on Stage 1
    showed that compression and seed blending hurt well-calibrated models.
    Use --recal and --seed-blend flags to experiment.

    Args:
        input_path: Path to the raw submission CSV.
        clip_min: Minimum probability after clipping.
        clip_max: Maximum probability after clipping.
        seed_blend: Weight for seed-based priors (0 = none, 0.15 = moderate).
        apply_recal: Whether to apply high-confidence compression.
        dry_run: If True, print stats but don't write output.

    Returns:
        Path to the calibrated output file, or None for dry runs.
    """
    df = pd.read_csv(input_path)
    df.columns = ["ID", "Pred"]
    original = df["Pred"].copy()

    print(f"Input: {input_path.name}")
    print(f"  {len(df)} rows")
    print(f"  Pred range: [{original.min():.4f}, {original.max():.4f}]")
    print(f"  Mean: {original.mean():.4f}, Median: {original.median():.4f}")

    # Extract season from IDs to load seeds
    sample_id = df["ID"].iloc[0]
    season = int(sample_id.split("_")[0])
    seeds = load_seeds(season)
    print(f"  Season: {season}, {len(seeds)} seeds loaded")

    # Step 1: High-confidence compression
    if apply_recal:
        df["Pred"] = df["Pred"].apply(recalibrate_high_confidence)
        changed = (df["Pred"] != original).sum()
        print(f"\n  Step 1 - High-confidence compression:")
        print(f"    {changed} predictions adjusted")

    # Step 2: Seed-based prior blending
    if seed_blend > 0 and seeds:
        blend_count = 0
        new_preds = df["Pred"].values.copy()

        for i, row in df.iterrows():
            parts = row["ID"].split("_")
            team_a = int(parts[1])
            team_b = int(parts[2])

            seed_a = seeds.get(team_a)
            seed_b = seeds.get(team_b)

            if seed_a is not None and seed_b is not None:
                prior = get_seed_prior(seed_a, seed_b)
                if prior is not None:
                    new_preds[i] = (1 - seed_blend) * new_preds[i] + seed_blend * prior
                    blend_count += 1

        df["Pred"] = new_preds
        print(f"\n  Step 2 - Seed prior blending ({seed_blend:.0%} weight):")
        print(f"    {blend_count} predictions blended with seed priors")
    else:
        print(f"\n  Step 2 - Seed prior blending: skipped")

    # Step 3: Clip extremes
    before_clip = df["Pred"].copy()
    df["Pred"] = df["Pred"].clip(clip_min, clip_max)
    clipped = (df["Pred"] != before_clip).sum()
    print(f"\n  Step 3 - Clipping [{clip_min}, {clip_max}]:")
    print(f"    {clipped} predictions clipped")

    # Summary stats
    print(f"\n  RESULT:")
    print(f"    Pred range: [{df['Pred'].min():.4f}, {df['Pred'].max():.4f}]")
    print(f"    Mean: {df['Pred'].mean():.4f}")

    # Distribution comparison
    bins = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
            (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
    print(f"\n    {'Band':<10} {'Before':>8} {'After':>8} {'Change':>8}")
    for lo, hi in bins:
        before_n = ((original >= lo) & (original < hi)).sum()
        after_n = ((df["Pred"] >= lo) & (df["Pred"] < hi)).sum()
        change = after_n - before_n
        if before_n > 0 or after_n > 0:
            print(f"    {lo:.0%}-{hi:.0%}    {before_n:>8} {after_n:>8} {change:>+8}")

    if dry_run:
        print("\n  DRY RUN - no file written")
        return None

    # Write calibrated output
    stem = input_path.stem
    output_path = input_path.parent / f"{stem}_calibrated.csv"
    df.to_csv(output_path, index=False)
    print(f"\n  Written to: {output_path.name}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Apply calibration corrections to a Kaggle submission CSV"
    )
    parser.add_argument("input", type=str, help="Path to the submission CSV")
    parser.add_argument("--clip-min", type=float, default=0.03,
                        help="Minimum probability (default: 0.03)")
    parser.add_argument("--clip-max", type=float, default=0.97,
                        help="Maximum probability (default: 0.97)")
    parser.add_argument("--seed-blend", type=float, default=0.0,
                        help="Weight for seed-based priors, 0 to disable (default: 0.0)")
    parser.add_argument("--recal", action="store_true",
                        help="Apply high-confidence compression (off by default)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing output")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    calibrate_submission(
        input_path,
        clip_min=args.clip_min,
        clip_max=args.clip_max,
        seed_blend=args.seed_blend,
        apply_recal=args.recal,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
