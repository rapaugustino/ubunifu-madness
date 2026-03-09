# Retraining Guide

Step-by-step instructions for retraining the model with fresh data — whether for a new season, updated game results, or improving the model.

## When to Retrain

| Scenario | What to Run | Time |
|----------|------------|------|
| New season starts | Full pipeline (Steps 1-7) | ~20 min |
| New Kaggle data drop | Steps 2-7 | ~15 min |
| Daily Elo updates (automatic) | `cron_elo_update.py` | ~30 sec |
| After Selection Sunday | Seeds refresh endpoint | ~5 sec |
| Model architecture changes | Steps 3-7 | ~15 min |

## Prerequisites

- Python 3.11+ with packages from `backend/requirements.txt`
- PostgreSQL database (local or Railway)
- Kaggle account for downloading competition data
- Jupyter for running the notebook

## Step 1: Download Fresh Data from Kaggle

Go to [March Machine Learning Mania 2025](https://www.kaggle.com/competitions/march-machine-learning-mania-2025/data) and download all CSV files.

Place them in `data/raw/`. Required files:

| File | Purpose |
|------|---------|
| `MRegularSeasonCompactResults.csv` | Men's game scores (1985-present) |
| `MRegularSeasonDetailedResults.csv` | Men's box scores (2003-present) |
| `MNCAATourneyCompactResults.csv` | Men's tournament results |
| `MNCAATourneyDetailedResults.csv` | Men's tournament box scores |
| `MNCAATourneySeeds.csv` | Men's tournament seeds |
| `MNCAATourneySlots.csv` | Men's bracket structure |
| `MTeams.csv` | Men's team IDs and names |
| `MTeamConferences.csv` | Men's conference membership by season |
| `MTeamCoaches.csv` | Men's coaching records |
| `MTeamSpellings.csv` | Name variant mappings |
| `MMasseyOrdinals.csv` | Computer ranking systems |
| `MConferenceTourneyGames.csv` | Conference tournament results |
| `Conferences.csv` | Conference names |
| `WRegularSeasonCompactResults.csv` | Women's equivalents... |
| `WRegularSeasonDetailedResults.csv` | |
| `WNCAATourneyCompactResults.csv` | |
| `WNCAATourneyDetailedResults.csv` | |
| `WNCAATourneySeeds.csv` | |
| `WNCAATourneySlots.csv` | |
| `WTeams.csv` | |
| `WTeamConferences.csv` | |

## Step 2: Regenerate Derived Statistics

This populates three database tables from the raw CSVs: Elo ratings, conference strength, and team season stats.

```bash
cd backend
python3 -m scripts.compute_stats
```

**What it does:**
1. Processes all regular season and tournament games chronologically
2. Computes Elo ratings for every team at end-of-season (snapshot_day=154)
3. Calculates conference strength metrics (avg_elo, depth, top5, non-conf winrate, tourney history)
4. Computes team season stats for the current season (Four Factors, efficiency, Massey rankings, momentum, coach info)

**Output:**
- `elo_ratings` table: ~15,000 rows (all teams, all seasons)
- `conference_strength` table: ~650 rows (all conferences, all seasons)
- `team_season_stats` table: ~700 rows (current season only)

**Time:** ~2 minutes

## Step 3: Run the ML Notebook

Open and run the Jupyter notebook:

```bash
cd notebooks
jupyter notebook Ubunifu_Madness_March_ML_Mania.ipynb
```

The notebook runs in order:

1. **Data loading** — Reads all CSVs, merges game results with seeds and features
2. **Feature engineering** — Builds the 27-feature matrix for all historical tournament matchups
3. **Elo parameter tuning** (optional) — Optuna search over K, home_adv, season_regression. Skip if using existing parameters.
4. **Model training** — Trains LR, LightGBM, XGBoost with leave-one-season-out CV
5. **Ensemble optimization** — Optuna search over ensemble weights
6. **Calibration** — Isotonic regression on out-of-fold predictions
7. **Submission generation** — Creates `stage1_submission_v2.csv` and `stage2_submission_v2.csv`

**Output:** Submission CSV in `submissions/` directory with format:
```
ID,Pred
2026_1101_1102,0.678
```

**Time:** ~5-10 minutes (longer if re-tuning Elo parameters)

## Step 4: Submit Predictions to Kaggle

Upload your submission CSVs to the Kaggle competition page for scoring.

```bash
# Install Kaggle CLI if not already
pip install kaggle

# Submit Stage 1 predictions (before tournament starts)
kaggle competitions submit \
  -c march-machine-learning-mania-2025 \
  -f submissions/stage1_submission_v2.csv \
  -m "Stage 1 - LR+LGB ensemble v2"

# Submit Stage 2 predictions (after Selection Sunday, when bracket is set)
kaggle competitions submit \
  -c march-machine-learning-mania-2025 \
  -f submissions/stage2_submission_v2.csv \
  -m "Stage 2 - LR+LGB ensemble v2"
```

**Stage 1 vs Stage 2:**
- **Stage 1**: Predictions for all possible team pairs. Scored on games played before Selection Sunday.
- **Stage 2**: Same format, but scored only on actual tournament games. You can update predictions between stages based on conference tournament results, injury news, etc.

Check your score on the [competition leaderboard](https://www.kaggle.com/competitions/march-machine-learning-mania-2025/leaderboard). Our model's Brier score benchmark is **0.1607** on historical cross-validation.

> **Tip:** You can submit up to 2 times per day. Submit Stage 1 early and iterate. For Stage 2, wait until after Selection Sunday when you have actual seeds to maximize accuracy.

## Step 5: Load Predictions into Database

```bash
cd backend
python3 -m scripts.load_predictions ../submissions/stage2_submission_v2.csv
```

**What it does:**
1. Clears existing v2 predictions from the `predictions` table
2. Parses each row: `SEASON_TEAMAID_TEAMBID` → season, team_a_id, team_b_id
3. Infers gender from team_a_id (< 2000 = Men's, >= 2000 = Women's)
4. Bulk inserts predictions in batches of 10,000

**Output:** ~140,000+ prediction rows (all possible team pairs for tournament-eligible teams)

## Step 6: Update ESPN Team Mappings

Only needed when new teams appear in the dataset or ESPN changes team IDs.

```bash
cd backend
python3 -m scripts.espn_team_mapper
```

**What it does:**
1. Fetches all NCAA basketball teams from ESPN API
2. Matches ESPN teams to Kaggle team IDs using name variants from `MTeamSpellings.csv`
3. Updates `espn_id`, `logo_url`, and `color` in the `teams` table
4. Saves mapping to `data/espn_team_map.json`

**Coverage:** ~355 men's teams, ~353 women's teams successfully mapped.

## Step 7: Verify

Check that everything loaded correctly:

```bash
# Backend health
curl http://localhost:8000/health

# Power rankings should show updated Elo
curl "http://localhost:8000/api/rankings/power?gender=M&limit=5"

# Predictions should return probabilities
curl "http://localhost:8000/api/predictions/1242/1211"

# Team details should have stats
curl "http://localhost:8000/api/teams/1242?season=2026"
```

## New Season Checklist

When a new season starts (e.g., transitioning from 2026 to 2027):

1. **Update SEASON constant** in these files:
   - `backend/scripts/compute_stats.py` — `SEASON = 2027`
   - `backend/scripts/update_elo_live.py` — `SEASON = 2027`
   - `backend/app/routers/espn.py` — `SEASON = 2027`

2. **Download new Kaggle CSVs** with the latest season's data

3. **Run the full pipeline** (Steps 2-6 above)

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

**Cron setup** (runs at 6 AM daily):
```
0 6 * * * cd /path/to/backend && python3 -m scripts.cron_elo_update >> /var/log/elo_update.log 2>&1
```

This processes yesterday's and today's completed games for both men's and women's, updates Elo ratings, team records, and conference strength metrics. It's idempotent — safe to run multiple times.

## Refreshing Win/Loss Records

To bulk-update all team records from ESPN (useful at start of season or after data issues):

```bash
curl -X POST "http://localhost:8000/api/records/refresh?gender=M"
curl -X POST "http://localhost:8000/api/records/refresh?gender=W"
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `compute_stats.py` fails on missing CSV | Kaggle data not downloaded | Download all CSVs to `data/raw/` |
| Predictions missing for some teams | Team pair not in submission CSV | Re-run notebook with updated team list |
| ESPN mapping gaps | New team or name change | Re-run `espn_team_mapper.py` |
| Elo ratings stale | Cron not running | Check cron logs, run manually |
| Duplicate game results | Script ran twice before commit | Deduplication is built-in, safe to re-run |
