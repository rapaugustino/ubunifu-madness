# Updating the Bracket for a New Season

This guide covers how to load tournament seeds and keep the bracket updated
once Selection Sunday happens.

## What the bracket needs

The bracket page reads from two database tables:

- **TourneySeed** — which 68 teams are in the tournament, their seed (1-16),
  and region (W/X/Y/Z). Loaded from Kaggle CSV.
- **GameResult** (game_type = "tourney") — tournament game results. These flow
  in automatically via the daily ESPN cron job once games are played.

The bracket router (`backend/app/routers/bracket.py`) handles everything else:
matchup structure (1v16, 8v9, etc.), play-in resolution, round advancement,
Final Four pairings, and win probability calculation.

## Step-by-step: Selection Sunday

### 1. Download updated Kaggle data

After Selection Sunday, Kaggle updates `MNCAATourneySeeds.csv` and
`WNCAATourneySeeds.csv` with the new season's seeds.

Download from:
https://www.kaggle.com/competitions/march-machine-learning-mania-2026/data

Place the updated CSVs in `data/raw/`.

### 2. Load seeds into the database

From the `backend/` directory, run:

```bash
python3 -m scripts.seed_db --seeds-only 2026
```

This loads only the 2026 tournament seeds (men's + women's) without touching
any other data. It's safe to re-run — existing seeds for that season are
replaced, not duplicated.

### 3. Verify

Visit the bracket page. It should now show the 2026 bracket with all 68 teams
in their correct regions and seed positions. Win probabilities come from:

- **Prediction table** (static model) if predictions exist for this season
- **Elo-based fallback** if no static predictions are loaded yet

### 4. (Optional) Load static model predictions

If you've generated new predictions from the ML model:

```bash
python3 -m scripts.import_predictions ../submissions/stage2_submission_v2.csv
```

This gives the bracket access to the full 31-feature model probabilities
instead of Elo-only estimates.

## During the tournament

Once the tournament starts, **everything is automatic**:

1. **Daily cron** (`cron_elo_update.py`) runs on Railway
2. ESPN returns tournament games with `gameType: "tourney"`
3. Games are saved as `GameResult(game_type="tourney")`
4. Bracket router reads these results and advances winners through each round
5. The bracket page updates in real-time — no manual intervention needed

Play-in games (First Four) are also handled automatically. If two teams share
a seed slot (e.g., two 16-seeds in the same region), the bracket resolves the
play-in winner from the game result.

## Timeline

| Date | Action | Manual? |
|------|--------|---------|
| Selection Sunday | Download Kaggle CSV, run `--seeds-only 2026` | Yes |
| (Optional) | Load updated model predictions | Yes |
| First Four | Games auto-ingested via ESPN cron | No |
| Round of 64 → Final | Games auto-ingested via ESPN cron | No |
| Championship | Final result auto-ingested | No |

## Troubleshooting

**Bracket shows last year's tournament:**
Seeds haven't been loaded for the current season. The bracket falls back to
the most recent season with seeds.

**Win probabilities all show 50%:**
No predictions loaded and no Elo ratings for the seeded teams. Run
`python3 -m scripts.compute_stats` to compute current Elo ratings.

**Missing a team:**
Check that the team exists in the `teams` table and has an entry in
`MNCAATourneySeeds.csv` for the correct season. Re-run `--seeds-only`.
