# Retraining Guide

Step-by-step instructions for retraining the model with fresh data — whether for a new season, updated game results, or improving the model.

## When to Retrain

| Scenario | What to Run | Time |
|----------|------------|------|
| New season starts | Full pipeline (Steps 1-8) | ~30 min |
| New Kaggle data drop | Steps 2-8 | ~20 min |
| Daily Elo updates (automatic) | `cron_elo_update.py` | ~30 sec |
| After Selection Sunday | Seeds refresh endpoint | ~5 sec |
| Model architecture changes | Steps 3-8 | ~20 min |

## Prerequisites

- Python 3.11+ with packages from `backend/requirements.txt`
- PostgreSQL database (local or Railway)
- Kaggle account for downloading competition data
- Jupyter for running the notebook

## Step 1: Download Fresh Data from Kaggle

Go to [March Machine Learning Mania](https://www.kaggle.com/competitions/march-machine-learning-mania-2025/data) and download all CSV files.

Place them in `data/raw/`. Required files:

| File | Purpose |
|------|---------|
| `MRegularSeasonCompactResults.csv` | Men's game scores (1985-present) |
| `MRegularSeasonDetailedResults.csv` | Men's box scores (2003-present) |
| `MNCAATourneyCompactResults.csv` | Men's tournament results |
| `MNCAATourneySeeds.csv` | Men's tournament seeds |
| `MTeams.csv` | Men's team IDs and names |
| `MTeamConferences.csv` | Men's conference membership by season |
| `MTeamCoaches.csv` | Men's coaching records |
| `MMasseyOrdinals.csv` | Computer ranking systems |
| `MConferenceTourneyGames.csv` | Conference tournament results |
| `Conferences.csv` | Conference names |
| `W*.csv` | Women's equivalents of all above |

## Step 2: Regenerate Derived Statistics

This populates three database tables from the raw CSVs: Elo ratings, conference strength, and team season stats.

```bash
cd backend
python3 -m scripts.compute_stats
```

**What it does:**
1. Processes all regular season and tournament games chronologically
2. Computes Elo ratings for every team at end-of-season (snapshot_day=154)
3. Calculates conference strength metrics (avg_elo, nc_winrate, tourney history)
4. Computes team season stats for the current season (Four Factors, efficiency, Massey, momentum, coach, SOS)
5. Runs `compute_advanced_stats()` which computes opponent-adjusted efficiency (AdjOE/AdjDE/AdjEM via 10-iteration algorithm), Barthag, Pythagorean win % and luck, consistency metrics (margin stdev, efficiency stdev), floor/ceiling (10th/90th percentile net efficiency), and upset vulnerability index for all teams

**Output:**
- `elo_ratings` table: ~15,000 rows (all teams, all seasons)
- `conference_strength` table: ~650 rows (all conferences, all seasons)
- `team_season_stats` table: ~700 rows (current season only)

**Time:** ~2 minutes

## Step 3: Run the V4 Notebook

Generate and run the V4 notebook:

```bash
cd notebooks
python3 generate_v4_notebook.py  # Generates and executes the notebook
```

The notebook runs in 7 parts:

1. **Data loading** — Reads all CSVs, merges game results with seeds, box scores, and Massey Ordinals
2. **Elo computation** — Computes Elo ratings for all teams across all seasons
3. **Feature engineering** — Builds the 40-feature matrix for ALL game types (regular + conf tourney + NCAA tourney) from 2012+
4. **Model training** — Season-based CV (train 2012-2022, validate 2023-2026), LR + LightGBM ensemble with isotonic calibration
5. **Evaluation** — Brier scores, accuracy, calibration curves, feature importance
6. **Final training** — Train on all 2012-2025 data, generate Kaggle submission CSVs
7. **Artifact export** — Save models to `artifacts/` directory (lr_v4.joblib, lgb_v4.joblib, calibrator_v4.joblib, model_metadata_v4.json)

**Key differences from V3:**
- Trains on ALL game types (163K games vs V3's 4.3K tournament-only)
- Game-type context as features (is_conf_tourney, is_ncaa_tourney, is_neutral_site)
- New features: rest_days, kenpom_rank, net_rank, consensus_rank, adj_eff_margin, barthag, quality_win_pct
- 40 features across 9 categories

**Output:**
- `artifacts/lr_v4.joblib`, `lgb_v4.joblib`, `calibrator_v4.joblib` — Model artifacts
- `artifacts/model_metadata_v4.json` — Feature columns, weights, config

**Time:** ~10-15 minutes

## Step 4: Submit Predictions to Kaggle

```bash
# Submit Stage 2 predictions (after Selection Sunday)
kaggle competitions submit \
  -c march-machine-learning-mania-2025 \
  -f submissions/stage2_submission_v3_modern.csv \
  -m "Stage 2 - V3 modern era LR+LGB ensemble"
```

**Stage 1 vs Stage 2:**
- **Stage 1**: All possible team pairs. Scored on games before Selection Sunday.
- **Stage 2**: Same format, scored on actual tournament games. Can update between stages.

## Step 5: Upload Model Artifacts to Database

This enables the live prediction pipeline to use the trained models instead of falling back to signal blending.

```bash
cd backend
python3 -m scripts.upload_model_artifacts --version v4 --artifact-dir ../notebooks/artifacts/
```

**What it does:**
1. Deactivates any existing active model artifacts
2. Uploads LR, LGB, and calibrator as binary blobs to the `model_artifacts` table
3. Stores feature columns and ensemble weights in metadata
4. Sets new artifacts as active

**After uploading:** Restart the server to clear the cached model bundle. New predictions will use the `ml_ensemble` path.

## Step 6: Load Predictions into Database

```bash
cd backend
python3 -m scripts.load_predictions ../submissions/stage2_submission_v4.csv
```

**What it does:**
1. Clears existing predictions from the `predictions` table
2. Parses each row: `SEASON_TEAMAID_TEAMBID` → season, team_a_id, team_b_id
3. Infers gender from team_a_id (< 3000 = Men's, >= 3000 = Women's)
4. Bulk inserts predictions in batches of 10,000

## Step 7: Regenerate Live Predictions (Optional)

If you want to re-lock predictions for past dates with the new model:

```bash
cd backend
# Dry run first to see what will be affected
python3 -m scripts.regenerate_predictions --from-date 20260308 --dry-run

# Run for real
python3 -m scripts.regenerate_predictions --from-date 20260308
```

This deletes old `GamePrediction` records and regenerates them by re-fetching each date from ESPN and running the new predictor. Outcomes are automatically re-resolved for completed games.

## Step 8: Verify

```bash
# Backend health
curl http://localhost:8000/health

# Power rankings should show updated Elo
curl "http://localhost:8000/api/rankings/power?gender=M&limit=5"

# Predictions should return probabilities
curl "http://localhost:8000/api/predictions/1242/1211"

# Performance summary should show ml_ensemble source
curl "http://localhost:8000/api/performance/summary"

# Test V3 predictions against past games
cd backend
python3 -m scripts.test_v3_predictions
```

## New Season Checklist

When a new season starts (e.g., transitioning from 2026 to 2027):

1. **Update SEASON constant** in these files:
   - `backend/scripts/compute_stats.py` — `SEASON = 2027`
   - `backend/scripts/update_elo_live.py` — `SEASON = 2027`
   - `backend/app/routers/espn.py` — `SEASON = 2027`
   - `backend/app/services/predictor.py` — `SEASON = 2027`

2. **Download new Kaggle CSVs** with the latest season's data

3. **Run the full pipeline** (Steps 2-7 above)

4. **After Selection Sunday** — refresh tournament seeds:
   ```bash
   curl -X POST "http://localhost:8000/api/seeds/refresh?gender=M"
   curl -X POST "http://localhost:8000/api/seeds/refresh?gender=W"
   ```

## Daily Elo Updates (Automated)

During the season, Elo ratings update automatically via cron:

```bash
# Manual run
cd backend
python3 -m scripts.cron_elo_update

# Or via API
curl -X POST "http://localhost:8000/api/elo/refresh?gender=M"
curl -X POST "http://localhost:8000/api/elo/refresh?gender=W"
```

**Cron pipeline** (`backend/scripts/cron_elo_update.py`) runs daily:
1. Elo rating updates from ESPN game results
2. Game result ingestion
3. Win/loss record updates
4. Player stats refresh
5. SOS (strength of schedule) recomputation
6. Advanced stats recomputation (AdjOE/AdjDE/AdjEM, Barthag, luck, consistency, floor/ceiling, upset vulnerability)

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `compute_stats.py` fails on missing CSV | Kaggle data not downloaded | Download all CSVs to `data/raw/` |
| Predictions all show same probability | Isotonic calibration clustering | V3 uses smooth calibration; ensure artifacts are uploaded |
| ESPN 500 error on scores | `headline` field is None | Fixed in V3: `game.get("headline") or ""` |
| ml_ensemble not used | Model artifacts not in DB | Run `upload_model_artifacts.py` and restart server |
| Conference tourney overconfidence | Model trained on NCAA tourney only (V3) | V4 trains on all game types with is_conf_tourney feature |
| Duplicate game results | Script ran twice before commit | Deduplication is built-in, safe to re-run |
