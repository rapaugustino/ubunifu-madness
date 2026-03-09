# 🏀 Ubunifu Madness — Project Architecture

> **Ubunifu Madness** — AI-Powered March Madness Predictions
> *Where machine learning meets bracketology.*

## Overview
**Ubunifu Madness** is a dual-purpose project: compete in Kaggle's March Machine Learning Mania 2026 **and** ship a polished, GenAI-powered web app that serves as an interactive bracket predictor, analytics dashboard, and AI basketball analyst. The app combines traditional ML predictions with Claude-powered natural language analysis and live web search — turning raw probabilities into something fans actually want to use.

**Brand Identity:**
- **Name**: Ubunifu Madness ("Ubunifu" = creativity/design in Swahili)
- **Tagline**: "AI-Powered March Madness Predictions"
- **Vibe**: Bold & competitive — Kaggle meets ESPN with an AI edge
- **Tone**: Opinionated, data-driven, fun. Like your smartest friend who also happens to have an ML model.
- **Logo concept**: "UM" monogram in a bold geometric style, or a basketball silhouette integrated with circuit/data motifs

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       FRONTEND                                │
│               Next.js + React + Tailwind                      │
│                                                               │
│  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Interactive  │  │ Dashboard│  │  Team    │  │  Bracket │ │
│  │  Bracket +    │  │ & Power  │  │  H2H    │  │  Chat    │ │
│  │  AI Analysis  │  │ Rankings │  │ Compare │  │  Agent   │ │
│  └──────┬───────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│         │               │             │              │        │
└─────────┼───────────────┼─────────────┼──────────────┼────────┘
          │               │             │              │
          ▼               ▼             ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI BACKEND                            │
│                                                               │
│  /api/predictions     - model win probabilities               │
│  /api/teams           - team stats, profiles, conference data │
│  /api/bracket         - bracket generation & Monte Carlo sim  │
│  /api/compare         - head-to-head matchup features         │
│  /api/chat            - proxy to Claude API (chat agent)      │
│  /api/analysis        - proxy to Claude API (matchup analysis)│
│  /api/leaderboard     - track prediction accuracy vs actual   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              ML MODEL LAYER                            │   │
│  │                                                        │   │
│  │  Feature Engineering → Model Inference                 │   │
│  │  (Elo, Conference Strength, KenPom-style, Seeds, etc.) │   │
│  │                                                        │   │
│  │  Models: Logistic Regression (baseline)                │   │
│  │          XGBoost / LightGBM (primary)                  │   │
│  │          Ensemble (final)                              │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              GenAI LAYER (Claude API)                   │   │
│  │                                                        │   │
│  │  Sonnet 4.5 — matchup analysis, chat agent             │   │
│  │  Haiku 4.5  — high-volume summaries, quick answers     │   │
│  │  Web Search — live expert takes, injury news            │   │
│  │  Prompt Caching — system prompt + team data cached      │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              DATA / STORAGE LAYER                      │   │
│  │                                                        │   │
│  │  PostgreSQL — teams, games, predictions, chat history   │   │
│  │  Redis — cached predictions, cached analyses, sessions  │   │
│  │  CSV/Parquet — raw Kaggle data                         │   │
│  └────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ubunifu-madness/
├── frontend/                        # Next.js app
│   ├── app/
│   │   ├── page.tsx                 # Landing / hero
│   │   ├── bracket/page.tsx         # Interactive bracket + AI analysis
│   │   ├── dashboard/page.tsx       # Analytics dashboard
│   │   ├── teams/[id]/page.tsx      # Team profiles
│   │   ├── compare/page.tsx         # Head-to-head
│   │   └── chat/page.tsx            # Bracket Chat Agent
│   ├── components/
│   │   ├── Bracket.tsx              # SVG/Canvas bracket visualization
│   │   ├── MatchupCard.tsx          # Game prediction card + AI button
│   │   ├── AIAnalysisPanel.tsx      # Claude-powered matchup breakdown
│   │   ├── ChatAgent.tsx            # Conversational bracket assistant
│   │   ├── TeamStats.tsx            # Radar chart, efficiency metrics
│   │   ├── WinProbBar.tsx           # Animated probability bar
│   │   ├── ConferenceView.tsx       # Conference strength visualization
│   │   ├── SimulationPanel.tsx      # Monte Carlo bracket sim
│   │   └── ExpertTakes.tsx          # Web search expert consensus
│   └── lib/
│       ├── api.ts                   # FastAPI client
│       ├── claude.ts                # Claude API client (analysis + chat)
│       └── types.ts                 # Shared types
│
├── backend/                         # FastAPI app
│   ├── app/
│   │   ├── main.py                  # App entrypoint
│   │   ├── routers/
│   │   │   ├── predictions.py
│   │   │   ├── teams.py
│   │   │   ├── bracket.py
│   │   │   ├── compare.py
│   │   │   ├── chat.py              # Claude chat proxy + context builder
│   │   │   └── analysis.py          # Claude analysis proxy
│   │   ├── models/                  # ML model loading / inference
│   │   │   ├── elo.py
│   │   │   ├── conference.py        # Conference strength calculations
│   │   │   ├── features.py          # Full feature engineering pipeline
│   │   │   └── ensemble.py
│   │   ├── genai/                   # GenAI integration
│   │   │   ├── prompts.py           # System prompts for analysis + chat
│   │   │   ├── context_builder.py   # Builds model context for Claude
│   │   │   └── cache.py             # Prompt caching strategy
│   │   ├── schemas/                 # Pydantic models
│   │   └── db/                      # Database models
│   └── scripts/
│       ├── train.py                 # Model training (Kaggle)
│       ├── generate_submission.py
│       ├── compute_conference_strength.py
│       └── backtest.py              # Historical Brier score eval
│
├── notebooks/                       # Kaggle EDA & experimentation
│   ├── 01_eda.ipynb
│   ├── 02_conference_strength.ipynb # Deep dive on conf metrics
│   ├── 03_feature_engineering.ipynb
│   ├── 04_model_training.ipynb
│   └── 05_ensemble_tuning.ipynb
│
├── data/                            # Kaggle datasets (gitignored)
│   ├── raw/
│   └── processed/
│
├── docker-compose.yml
└── README.md
```

---

## ML Pipeline (Kaggle Competition)

### Feature Engineering Strategy

| Feature Group | Description | Source Files |
|---|---|---|
| **Elo Ratings** | Season-long Elo with configurable K-factor, home advantage, margin-of-victory adjustment. Reset between seasons with regression to mean. | CompactResults |
| **Conference Strength** | See detailed breakdown below — multi-layered conference metrics | Conferences, Results, MasseyOrdinals |
| **Seed Features** | Seed number, seed difference, historical seed-vs-seed win rates (e.g., 5v12 upset rate) | NCAATourneySeeds |
| **Box Score Aggregates** | Per-game averages: FG%, 3PT%, FT%, rebounds, turnovers, assists, blocks, steals | DetailedResults |
| **Advanced Metrics (Four Factors)** | Offensive/defensive efficiency, tempo, eFG%, TO%, OR%, FT rate — the "KenPom-style" features | DetailedResults |
| **Massey Ordinals** | Rankings from top systems (POM, SAG, RPI, MOR, WOL). Use last pre-tourney ranking (DayNum=133) | MMasseyOrdinals |
| **Momentum** | Last-10-games win%, conference tourney performance, scoring trend (increasing/decreasing) | CompactResults |
| **Coach Experience** | Tournament appearances, career tournament win%, years at current school | MTeamCoaches |
| **Geography / Travel** | Distance from team's home to game city (proxy for travel fatigue / crowd advantage) | Cities, GameCities |

### Conference Strength — Deep Dive

Conference strength is critical for calibrating teams that play in vastly different competitive environments. A 25-5 record in the Big 12 is very different from a 25-5 record in the Southland.

**Metrics to compute (per conference, per season):**

1. **Conference Elo Average** — Mean Elo of all teams in the conference. Simple and effective baseline.

2. **Conference Elo Depth** — Standard deviation of Elo within the conference. Low StdDev = deep conference (everyone is competitive). High StdDev = top-heavy.

3. **Top-N Elo** — Average Elo of the top 3-5 teams in the conference. Captures "elite tier" strength even in uneven conferences.

4. **Non-Conference Win Rate** — How the conference performs in aggregate against out-of-conference opponents. Arguably the purest signal because it directly measures cross-conference performance.
   ```python
   # For each conference, compute:
   conf_games = games where one team is in conf and opponent is NOT
   conf_nc_winrate = wins / total_conf_games
   ```

5. **Massey Ordinal Conference Rank** — Average ranking of conference teams across multiple Massey systems (POM, SAG, etc.). More robust than any single ranking.

6. **Historical Tournament Performance** — Conference-level win rate in the NCAA tournament over the past 3-5 years. Captures "March culture" — some conferences consistently over/underperform their regular season metrics.

7. **Conference Tournament Competitiveness** — Number of games decided by 5 points or fewer in the conference tournament. Proxy for how battle-tested teams are heading into March.

**How to use these as features:**

- For each team in a matchup, attach their conference's metrics as features
- Compute **conference strength differential** between the two teams' conferences
- Create interaction features: `team_elo × conf_strength` (a good team in a good conference is worth more than a good team in a weak conference)
- Use non-conference win rate as an **adjustment factor** to normalize raw win-loss records

**Implementation sketch:**

```python
def compute_conference_strength(season, conf_abbrev, results_df, teams_conf_df, elo_dict):
    """Compute multi-dimensional conference strength metrics."""
    conf_teams = teams_conf_df[
        (teams_conf_df.Season == season) & (teams_conf_df.ConfAbbrev == conf_abbrev)
    ].TeamID.tolist()

    # 1. Elo-based metrics
    conf_elos = [elo_dict.get((season, tid), 1500) for tid in conf_teams]
    avg_elo = np.mean(conf_elos)
    elo_depth = np.std(conf_elos)
    top5_elo = np.mean(sorted(conf_elos, reverse=True)[:5])

    # 2. Non-conference win rate
    season_games = results_df[results_df.Season == season]
    nc_wins, nc_total = 0, 0
    for _, game in season_games.iterrows():
        w_conf = get_conf(game.WTeamID, season)
        l_conf = get_conf(game.LTeamID, season)
        if w_conf != l_conf:  # Non-conference game
            if w_conf == conf_abbrev:
                nc_wins += 1; nc_total += 1
            elif l_conf == conf_abbrev:
                nc_total += 1
    nc_winrate = nc_wins / max(nc_total, 1)

    # 3. Massey ordinal average
    conf_rankings = massey_df[
        (massey_df.Season == season) &
        (massey_df.TeamID.isin(conf_teams)) &
        (massey_df.RankingDayNum == 133)  # Final pre-tourney rankings
    ].groupby('TeamID').OrdinalRank.mean()
    massey_avg = conf_rankings.mean()

    return {
        'conf_avg_elo': avg_elo,
        'conf_elo_depth': elo_depth,
        'conf_top5_elo': top5_elo,
        'conf_nc_winrate': nc_winrate,
        'conf_massey_avg': massey_avg,
    }
```

### Model Stack

1. **Baseline** — Logistic Regression on seed difference (sanity check, ~0.24 Brier)
2. **Primary** — XGBoost with full feature set, tuned via Optuna
3. **Secondary** — LightGBM for diversity (different tree-building algorithm)
4. **Ensemble** — Weighted average, weights optimized on historical Brier score (2021-2025)

### Evaluation

- **Metric**: Brier Score (equivalent to MSE for binary outcomes)
- **Validation**: Leave-one-season-out CV (train on all seasons except target, predict target tournament)
- **Target**: Brier < 0.20 (competitive range; top Kaggle submissions typically 0.15-0.18)
- **Ablation testing**: Measure Brier improvement from each feature group to understand marginal value

### Kaggle Submission Workflow

```python
# generate_submission.py (simplified)
for season in [2026]:
    teams = get_all_d1_teams(season)  # All D1 teams, not just tourney
    for team_i, team_j in all_pairs(teams):
        lower_id = min(team_i, team_j)
        higher_id = max(team_i, team_j)
        features = build_features(lower_id, higher_id, season)
        pred = ensemble.predict_proba(features)
        submissions.append(f"{season}_{lower_id}_{higher_id},{pred}")
```

---

## Kaggle Competition Strategy

### Understanding the 2026 Format

This year's format has key differences from prior years that affect strategy:

1. **All pairwise predictions required** — You predict every possible D1 matchup (not just 68 tournament teams). This means ~350+ teams × all pairs = ~60,000+ predictions for men's alone, plus women's. Your model must generalize to *any* matchup, including teams that won't make the tournament.

2. **Combined men's + women's** — One submission file covers both tournaments. Women's basketball has different dynamics (pace, scoring, upset frequency), so separate models or a gender feature is important.

3. **Submit anytime before March 19** — No more scrambling after Selection Sunday. You can submit early and iterate. But you MUST manually select your 2 final submissions — don't rely on auto-selection.

4. **Brier score evaluation** — Equivalent to MSE for probabilities. Key implication: you want *calibrated* probabilities, not just correct rankings. A prediction of 0.65 that's right is better than a prediction of 0.95 that's right, because the 0.95 is penalized harder when it's wrong.

### Submission Timeline & Data Strategy

```
Feb 19 ─── Competition opens
   │
   ├── Week 1: Submit baseline (Elo-only model, ~0.24 Brier)
   │           Purpose: validate format, establish floor
   │
   ├── Week 2: Submit full-feature model (XGBoost + conference strength)
   │           Purpose: see improvement, identify weak spots
   │
   ├── ~Mar 5-10: Kaggle releases updated season data
   │              (games through late February / early March)
   │
   ├── Week 3: Retrain on updated data, tune ensemble
   │           Submit ensemble model
   │
   ├── Mar 15: Selection Sunday (DayNum=132)
   │           Tournament field is set — seeds revealed
   │           KEY: Your model already has predictions for all pairs,
   │           but now you know which pairs actually matter.
   │           Optional: retrain one final time with conf tourney results
   │
   ├── ~Mar 17-18: Kaggle releases final data update
   │
   ├── Mar 19 4PM UTC: FINAL SUBMISSION DEADLINE ⚠️
   │           Select your best 2 submissions manually!
   │
   └── Mar 19 - Apr 6: Watch results, leaderboard updates live
```

### Stage 1 vs Stage 2

- **Stage 1 (leaderboard before tournament)**: Scored on 2021-2025 historical data. Use this to validate your model's backtesting performance. Your 2026 predictions score 0.0 until games are played.
- **Stage 2 (live tournament)**: As 2026 games are played, Kaggle rescores. This is what matters for prizes/medals.

**Implication**: A model that backtests well on 2021-2025 is necessary but not sufficient. Recency matters — 2024-2025 patterns may be more predictive than 2010 patterns. Consider weighting recent seasons higher during training.

### Key Competition Tactics

1. **Calibration over accuracy** — Use Platt scaling or isotonic regression to calibrate your ensemble's output probabilities. A well-calibrated 0.60 is better than an overconfident 0.85 in Brier score.

2. **Ensemble diversity** — Combine models that make *different* errors. XGBoost + LightGBM + logistic regression with different feature sets provides more diversity than three XGBoost models with different hyperparameters.

3. **Don't overfit to tournament games** — Regular season games vastly outnumber tournament games. Train on regular season + tournament, but validate on tournament only (that's what Brier score measures).

4. **Handle the all-pairwise format** — Many predicted matchups will never happen. But the model must still produce reasonable probabilities for e.g., a 1-seed vs a 16-seed from a different region. Seed difference and Elo difference handle this naturally.

5. **Women's data considerations** — Less historical data (starts 1998 for compact, 2010 for detailed). Conference dynamics differ. Consider: separate women's model OR shared model with women-specific features.

6. **Late-season signal** — The final Kaggle data update (~Mar 17-18) includes conference tournament results. Conference tournament performance is one of the strongest predictive signals for March Madness. Prioritize a fast retrain pipeline.

```python
# Quick retrain script for data updates
def retrain_on_update(data_dir="data/raw/"):
    """Retrain pipeline triggered when Kaggle drops new data."""
    # 1. Reload all CSVs
    data = load_kaggle_data(data_dir)
    
    # 2. Recompute Elo (runs through all games including new ones)
    elo_ratings = compute_elo(data['compact_results'])
    
    # 3. Recompute conference strength (includes conf tourney games)
    conf_strength = compute_all_conference_strength(data, elo_ratings)
    
    # 4. Rebuild features for 2026
    features_2026 = build_features_for_season(2026, data, elo_ratings, conf_strength)
    
    # 5. Retrain ensemble (warm-start from previous weights)
    ensemble = retrain_ensemble(features_2026, warm_start=True)
    
    # 6. Generate fresh submission
    submission = generate_submission(ensemble, features_2026)
    submission.to_csv(f"submissions/submission_{datetime.now():%Y%m%d_%H%M}.csv")
    
    # 7. Update web app predictions via API
    update_predictions_api(submission)
    
    return submission
```

---

## Kaggle Competition Strategy

### Understanding the Format

This year's competition has key differences from prior years that affect strategy:

1. **Combined Men's + Women's** — Single submission file covers both tournaments. Need strong predictions for both, not just men's.
2. **All pairwise matchups** — You predict every possible team-vs-team outcome (~125K+ rows for men, ~100K+ for women), not just tournament teams. This means your model must generalize to any D1 matchup, including teams that won't make the tournament.
3. **Brier Score evaluation** — Equivalent to MSE on probabilities. Penalizes overconfident wrong predictions heavily: predicting 0.95 and being wrong costs 0.9025, while predicting 0.6 and being wrong costs only 0.16.
4. **Two selected submissions** — You pick which two submissions count. Don't rely on auto-selection.

### Calibration Matters More Than Accuracy

Because Brier score punishes overconfidence, **well-calibrated probabilities beat sharp predictions**:

- A model predicting 0.65 for every game where the better team wins will score better than one that predicts 0.90 and is occasionally wrong
- **Platt scaling** or **isotonic regression** on top of raw model outputs can significantly improve calibration
- Log-loss and Brier score are related but not identical — optimize directly for Brier

```python
# Post-hoc calibration
from sklearn.calibration import CalibratedClassifierCV

calibrated_model = CalibratedClassifierCV(
    base_model, method='isotonic', cv=5
)
calibrated_model.fit(X_train, y_train)

# Verify calibration with reliability diagram
from sklearn.calibration import calibration_curve
fraction_pos, mean_predicted = calibration_curve(y_test, preds, n_bins=10)
```

### Submission Strategy & Timeline

```
Feb 19 (Start) ─────────────────────── Mar 19 4PM UTC (Deadline)
  │                                           │
  ├─ Feb 25: First baseline submission        │
  │          (Elo-only, just to get on board)  │
  │                                           │
  ├─ Mar 3: Full feature set submission       │
  │          (Elo + conf strength + box scores)│
  │                                           │
  ├─ Mar 10: Ensemble v1 submission           │
  │           (XGBoost + LightGBM blend)      │
  │                                           │
  ├─ ~Mar 15: Kaggle releases updated data    │
  │           (includes late-season games,     │
  │            conf tourney results)           │
  │                                           │
  ├─ Mar 15: Selection Sunday                 │
  │          Now we know the actual 68 teams   │
  │          Seeds are revealed                │
  │                                           │
  ├─ Mar 16-18: CRITICAL WINDOW              │
  │   - Retrain on updated data               │
  │   - Incorporate actual seeds              │
  │   - Re-run ensemble with latest features  │
  │   - Check for injured players via web     │
  │     search → manual adjustments           │
  │   - Submit final predictions              │
  │                                           │
  └─ Mar 19 4PM UTC: SELECT 2 SUBMISSIONS    │
      - One "safe" (well-calibrated ensemble) │
      - One "bold" (slightly more aggressive  │
        on upset predictions)                 │
```

### Stage 1 vs Stage 2

- **Stage 1** (pre-tournament): Leaderboard scores on historical data (2021-2025 tournaments). Use this to validate your model against known outcomes. Your Stage 1 score gives you a good estimate of real performance.
- **Stage 2** (tournament): The 2026 predictions get scored as real games happen. Kaggle periodically rescores. Your 2026 rows show 0.0 until games are played.

**Key insight**: Stage 1 performance on 2021-2025 is your best proxy. If your leave-one-season-out CV gives Brier ~0.18 and your Stage 1 leaderboard is ~0.18, your model is well-calibrated. If there's a big gap, you're overfitting.

### The All-Pairwise Problem

With ~350+ men's D1 teams and ~350+ women's teams, you're predicting ~61K men's matchups and ~61K women's matchups. Most of these will never happen, but you still need reasonable predictions.

**Strategies:**
- Your Elo + feature model naturally handles arbitrary matchups (it doesn't depend on teams having played each other)
- Conference strength is extra valuable here — for teams you know little about, their conference is a strong signal
- For very weak teams (low-major conference, limited data), regression toward seed/conference priors prevents wild predictions
- **Clip predictions** to [0.02, 0.98] — never predict absolute certainty; Brier severely punishes a confident wrong prediction

```python
# Clipping is critical for Brier score
preds = np.clip(ensemble.predict_proba(X)[:, 1], 0.02, 0.98)
```

### Competition Edge: What Top Kaggle Entries Do

Based on past years' winning solutions:
1. **Elo is king** — nearly every top solution includes Elo. Your configurable K-factor and margin-of-victory adjustments are table stakes.
2. **Massey ordinals are high-signal** — especially POM (Pomeroy), SAG (Sagarin), and MOR (Massey's own). Average across multiple systems.
3. **Seed features have diminishing returns** — seed difference is powerful but everyone uses it. The edge comes from *seed interaction features* (e.g., historical 5-vs-12 upset rates).
4. **Women's data is sparser** — fewer seasons of detailed results (since 2010 vs 2003). Models that handle the women's side well gain an edge since many competitors focus on men's.
5. **Late-season data matters** — the Kaggle data update ~Mar 15 includes conference tournament results. Teams that win their conf tourney are on a hot streak; injured stars get exposed. Retraining on this data is mandatory.

### Shared Pipeline: Kaggle ↔ Web App

The same model that generates the Kaggle submission powers the web app:

```python
# scripts/generate_submission.py
predictions = generate_all_pairwise(model, season=2026)
save_kaggle_csv(predictions, "submission.csv")

# Also save to database for web app
save_to_postgres(predictions, table="predictions")

# Trigger web app cache refresh
invalidate_redis_cache("predictions:2026")
```

This means every time you retrain for Kaggle, the web app automatically gets updated predictions.

---

## GenAI Layer — Claude Integration

### Overview

The GenAI layer is what transforms this from "another bracket app" into an AI product. The ML model makes predictions; Claude explains, contextualizes, and interacts.

**Principle: ML predicts, LLM explains.** Never let the LLM override the model's predictions. Claude's job is to make the model's output accessible, interesting, and actionable.

### Feature 1: AI Matchup Analysis

When a user clicks on any matchup, Claude generates a 3-4 paragraph analysis grounded in the model's features.

**How it works:**

```
User clicks matchup → FastAPI builds context payload:
  - Both teams' stats (Elo, efficiency, conf strength, seed, record, streak)
  - Model's predicted win probability
  - Key feature differentials (where the model sees the biggest gaps)
  - Conference strength comparison
→ Context sent to Claude Sonnet with system prompt
→ Claude generates analysis in natural language
→ Displayed in slide-over panel on the bracket
```

**System prompt (stored in `backend/genai/prompts.py`):**

```
You are a sharp college basketball analyst for a March Madness prediction app.
You write punchy, insightful matchup analysis — like a mix of Bill Simmons
and Nate Silver. Use the model's data to explain WHY the prediction makes
sense (or where it might be wrong). Keep it to 3-4 paragraphs. No markdown
headers or bullet points. Be specific about basketball: pace, defense,
shooting, rebounding, turnover margin. End with a bold prediction line.
```

**Cost:** ~$0.002 per analysis (Sonnet, ~500 input + ~400 output tokens)

### Feature 2: Expert Takes (Web Search)

Uses Claude's web search tool to find what real analysts are saying about the matchup.

```
User clicks "Expert Takes" tab → Claude API call with web_search tool:
  - Searches for recent analysis on both teams
  - Synthesizes expert opinions
  - Highlights where experts agree/disagree with the model
→ Displayed alongside model analysis
```

**Cost:** ~$0.01 per search (web search fee + token costs)

**Caching strategy:** Cache expert takes for 2 hours per team pair. During the tournament, reduce to 30 min (news moves fast).

### Feature 3: Bracket Chat Agent ⭐ (Key Differentiator)

A conversational AI assistant that helps users build their bracket using the model's predictions as grounding context.

**What users can ask:**

- "Who should I pick in the East region?"
- "What's the best Cinderella pick this year?"
- "Give me a bold upset to pick in Round 1"
- "How does Duke match up against mid-majors?"
- "Which 12-seed is most likely to pull an upset?"
- "Build me a bracket that maximizes upsets"
- "What's my bracket's expected score?"
- "Compare my picks to the AI's picks"

**Architecture:**

```
┌──────────────────────────────────────────────────┐
│                CHAT AGENT FLOW                    │
│                                                   │
│  User message                                     │
│       │                                           │
│       ▼                                           │
│  FastAPI /api/chat                                │
│       │                                           │
│       ├─→ context_builder.py                      │
│       │     Assembles relevant model predictions, │
│       │     team stats, conference data, user's   │
│       │     current bracket picks                 │
│       │                                           │
│       ├─→ Claude Sonnet API call                  │
│       │     System prompt: basketball analyst     │
│       │     + JSON context of model predictions   │
│       │     + web_search tool (optional)          │
│       │     + conversation history                │
│       │                                           │
│       └─→ Response streamed to frontend           │
│             via SSE (Server-Sent Events)           │
└──────────────────────────────────────────────────┘
```

**Context builder (critical for quality):**

The chat agent's power comes from feeding Claude the right context. For each user message, the backend determines what model data is relevant:

```python
def build_chat_context(user_message, user_bracket, model_predictions):
    """Build context payload for Claude based on the user's question."""
    context = {
        "model_top_picks": {
            "champion": get_champion_probabilities(model_predictions),
            "final_four": get_final_four_probabilities(model_predictions),
            "biggest_upsets": get_predicted_upsets(model_predictions),
        },
        "user_bracket": user_bracket,  # Their current picks
        "user_vs_model_disagreements": find_disagreements(
            user_bracket, model_predictions
        ),
    }

    # Add relevant team/conference data based on entities in the message
    mentioned_teams = extract_team_mentions(user_message)
    mentioned_conferences = extract_conf_mentions(user_message)

    if mentioned_teams:
        context["team_profiles"] = {
            t: get_team_profile(t) for t in mentioned_teams
        }
    if mentioned_conferences:
        context["conference_data"] = {
            c: get_conf_strength(c) for c in mentioned_conferences
        }

    # If asking about upsets or Cinderellas, include mid-major data
    if any(kw in user_message.lower()
           for kw in ["upset", "cinderella", "sleeper", "dark horse"]):
        context["upset_candidates"] = get_upset_candidates(model_predictions)
        context["conference_overperformers"] = get_conf_tournament_history()

    return context
```

**Chat system prompt:**

```
You are a college basketball analyst and bracket advisor powering a March
Madness prediction app. You have access to an ML model's predictions and
team statistics. When giving advice:

1. Always ground your recommendations in the model's data (cite specific
   probabilities and stats)
2. Explain your reasoning in terms of basketball (pace, efficiency,
   matchup advantages)
3. When the user's picks disagree with the model, flag it — but respect
   their autonomy
4. For upset picks, reference conference strength and historical
   seed-vs-seed upset rates
5. Be opinionated and fun — this is March Madness, not a corporate memo
6. You can use web search to check for injuries, suspensions, or breaking
   news when relevant

You do NOT make predictions yourself. You explain and contextualize the
ML model's predictions. If asked for a pick, say "The model gives X a Y%
chance because..." not "I think X will win."
```

**Cost:** ~$0.005-0.01 per message (slightly higher due to conversation history). With prompt caching on the system prompt + team data, follow-up messages are ~60% cheaper.

### Feature 4: Upset Explainer

When the model predicts an upset (lower seed winning), auto-generate a brief explanation grounded in feature importance.

```python
# When pred < 0.5 for the favored seed:
upset_context = {
    "favorite": team_a_stats,
    "underdog": team_b_stats,
    "model_prob": pred,
    "key_factors": get_shap_top_features(model, features),
    "conference_strength_gap": conf_a_strength - conf_b_strength,
    "historical_seed_upset_rate": get_seed_matchup_history(seed_a, seed_b),
}
# Claude generates: "The model sees Utah St pulling the upset because..."
```

### GenAI Cost Summary

| Feature | Model | Cost/call | Frequency | Monthly est. (1K DAU) |
|---|---|---|---|---|
| Matchup Analysis | Sonnet 4.5 | ~$0.002 | 5/user/day | $300 |
| Expert Takes | Sonnet + Web Search | ~$0.01 | 2/user/day | $600 |
| Chat Agent | Sonnet 4.5 | ~$0.005-0.01 | 8 msgs/user/day | $1,200-2,400 |
| Upset Explainer | Haiku 4.5 | ~$0.001 | Auto-generated | $50 |

**Total estimated: ~$2,000-3,300/month at 1K DAU during tournament**

**Optimization levers:**
- **Prompt caching**: Cache system prompts + team data → 90% savings on cached portion
- **Haiku fallback**: Use Haiku for simpler tasks (summaries, quick stats) at $1/$5 per MTok
- **Response caching**: Cache analyses in Redis (same matchup = same analysis for 2 hours)
- **Rate limiting**: Cap free users at 10 AI analyses/day, unlimited for registered users
- **Batch API**: Pre-generate all 64 first-round analyses at 50% discount before tournament starts

With caching + Haiku fallback, realistic cost is closer to **$500-800/month** for the 3-week tournament window.

---

## Web App Features

### 1. Interactive Bracket Predictor + AI Analysis
- Visual 64-team bracket (men's + women's)
- Click to advance teams OR let the AI auto-fill
- Toggle between "AI picks" and "my picks" mode
- **AI Analysis button on every matchup** — opens Claude-powered breakdown
- **Expert Takes tab** — live web search for analyst opinions
- Monte Carlo simulation: run 10K brackets, show % each team reaches each round
- Upset probability highlights (color-coded)

### 2. Analytics Dashboard
- **Team Power Rankings** — sortable by Elo, efficiency, conference strength
- **Conference Strength Rankings** — sortable by avg Elo, depth, non-conf win rate, Massey avg
- **Prediction Heatmap** — matrix of all pairwise win probabilities
- **Historical Accuracy** — how the model performed backtested on past years
- **Live Tournament Tracker** — predictions vs actual as games are played

### 3. Team Explorer & Conference View
- Individual team profile pages with radar charts (offense, defense, tempo, experience, conf strength)
- Season trajectory (Elo over time)
- Key wins/losses with opponent quality context
- **Conference context page** — how team's conference ranks, and how that adjusts the team's profile

### 4. Head-to-Head Comparisons
- Select two teams → see AI win probability + feature breakdown
- "Why does the model favor Team X?" — SHAP-style feature importance
- **Conference strength comparison** — "Duke plays in a conf averaging 1720 Elo vs Utah St's 1580"
- One-click AI analysis from comparison view

### 5. Bracket Chat Agent ⭐
- Conversational AI assistant grounded in model predictions
- Helps users build brackets, find upsets, understand matchups
- Can search the web for injuries and breaking news
- Compares user's bracket to AI bracket and flags disagreements
- Streaming responses via SSE for real-time feel

---

## What Makes This App Stand Out

### vs. Other Bracket Apps (ESPN, Yahoo, CBS)
| Feature | ESPN/Yahoo/CBS | This App |
|---|---|---|
| Win probabilities | ❌ or basic | ✅ ML model with 9+ feature groups |
| Natural language analysis | ❌ | ✅ Claude explains every matchup |
| Live expert consensus | ❌ | ✅ Web search synthesizes analyst takes |
| Conference strength viz | ❌ | ✅ Multi-dimensional conf metrics |
| Chat assistant | ❌ | ✅ "Who should I pick?" with model context |
| Model transparency | ❌ | ✅ SHAP values, feature breakdowns |
| Monte Carlo sim | ❌ | ✅ 10K simulated tournaments |
| Model vs Expert disagreements | ❌ | ✅ Highlighted when model diverges from consensus |

### vs. Other Kaggle Projects
Most Kaggle competitors stop at a Jupyter notebook. This project goes notebook → API → production web app → GenAI layer. That's four levels deeper.

### The "Wow Factor" Features
1. **"The model disagrees with ESPN"** — When your model's prediction diverges from expert consensus, highlight it prominently. These disagreements are the most compelling and shareable content.
2. **Bracket Chat Agent** — No one else has this. A conversational AI that knows your model's predictions and helps users fill out their bracket is genuinely novel.
3. **Conference Strength Explorer** — Interactive visualization showing why a 25-5 Big 12 team is very different from a 25-5 Southland team. Educational and useful.
4. **Live Upset Tracker** — During the tournament, show which of your predicted upsets actually happened. Real-time model validation.
5. **"What Would Have Happened?"** — Counterfactual analysis: "If Gonzaga had been in the Big 12 this year, our model estimates their Elo would be X instead of Y."
6. **Shareable Bracket Cards** — Generate social-media-friendly images of bracket picks with AI analysis snippets. Viral potential during March.

### Portfolio Differentiators
1. **ML + GenAI integration** — Shows you understand when to use traditional ML vs LLMs and how to combine them
2. **Conference strength feature engineering** — Domain-specific, multi-layered feature requiring basketball knowledge
3. **Production architecture** — Deployed product with caching, rate limiting, streaming, proxied API calls
4. **Cost-conscious design** — Prompt caching, Haiku fallback, Redis caching shows you think about scale
5. **Full-stack execution** — React, FastAPI, PostgreSQL, Redis, Anthropic API, Vercel, Railway

---

## Deployment & Scalability Architecture

### Target Scale

The app needs to handle **bursty traffic** — March Madness drives massive spikes. Selection Sunday, Round 1, and Final Four weekends can see 10-100x normal traffic within hours.

| Scenario | DAU | Concurrent | Req/min | Notes |
|---|---|---|---|---|
| Pre-tournament (baseline) | 100-500 | 20-50 | 50-200 | Building brackets |
| Selection Sunday spike | 5K-10K | 1K-2K | 2K-5K | Everyone checks predictions |
| Round 1 (Thu/Fri) | 10K-50K | 2K-5K | 5K-10K | Peak as games tip off |
| Sweet 16 / Final Four | 5K-20K | 1K-3K | 3K-8K | High but less chaotic |
| Post-tournament | 50-100 | 10 | 20 | Portfolio visitors |

### Infrastructure Stack

```
                         ┌─────────────┐
                         │  Cloudflare  │
                         │  CDN / DDoS  │
                         └──────┬──────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
        ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
        │   Vercel     │  │   Vercel    │  │   Vercel    │
        │  Edge Node   │  │  Edge Node  │  │  Edge Node  │
        │  (frontend)  │  │  (frontend) │  │  (frontend) │
        └──────┬──────┘  └─────┬──────┘  └──────┬──────┘
               │               │                │
               └───────────────┼────────────────┘
                               │
                      ┌────────▼────────┐
                      │  Load Balancer   │
                      │  (Fly.io proxy)  │
                      └────────┬────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │  FastAPI     │ │  FastAPI     │ │  FastAPI     │
       │  Instance 1  │ │  Instance 2  │ │  Instance N  │
       │  (1 vCPU,    │ │  (auto-      │ │  (auto-      │
       │   512MB)     │ │   scaled)    │ │   scaled)    │
       └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
              │               │                │
              └───────────────┼────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
     ┌──────▼──────┐  ┌──────▼──────┐  ┌───────▼───────┐
     │  PostgreSQL  │  │   Redis     │  │  Claude API   │
     │  (Neon)      │  │  (Upstash)  │  │  (Anthropic)  │
     │              │  │             │  │               │
     │  - Teams     │  │  - Pred     │  │  - Sonnet 4.5 │
     │  - Games     │  │    cache    │  │  - Haiku 4.5  │
     │  - Preds     │  │  - Analysis │  │  - Web Search │
     │  - Users     │  │    cache    │  │               │
     │  - Brackets  │  │  - Sessions │  │               │
     │              │  │  - Rate     │  │               │
     │              │  │    limits   │  │               │
     └─────────────┘  └─────────────┘  └───────────────┘
```

### Scalability by Layer

**Frontend (Vercel)**
- Next.js with SSR for initial load, client-side for interactivity
- Static generation (ISG) for team profile pages — regenerated every 30 min
- Edge functions for lightweight API proxying (reduces backend load)
- Vercel's CDN handles global distribution and traffic spikes natively
- Bracket state stored client-side (localStorage + optional server sync)

**Backend (Fly.io)**
- Auto-scales based on concurrent connections (min 1, max 10 machines)
- Each machine: 1 shared vCPU, 512MB RAM (pickled XGBoost is ~5MB)
- **Stateless design** — no session affinity needed, any instance serves any request
- Model loaded into memory at startup (cold start ~3s, warm instant)
- Geographic distribution: deploy to `iad` (US East) + `lax` (US West)

```toml
# fly.toml
[http_service]
  internal_port = 8000
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[services.concurrency]
  type = "connections"
  hard_limit = 100
  soft_limit = 80
```

**Database (Neon Postgres)**
- Serverless Postgres — scales to zero when idle, scales up on demand
- Connection pooling via built-in PgBouncer
- Read replicas for analytics queries (dashboard, leaderboard)
- Predictions table is write-once (on retrain), read-many — ideal for caching

**Cache Layer (Upstash Redis)**
- Serverless Redis — pay per request, no idle cost
- Global replication across regions
- **Cache hierarchy:**

```
Request flow:
  1. Check Redis for cached response (< 1ms)
  2. If miss → check in-memory model cache (< 5ms)
  3. If miss → compute from model (< 50ms)
  4. If GenAI → check Redis for cached analysis (< 1ms)
  5. If miss → call Claude API (1-3s)
  6. Cache result in Redis with TTL
```

| Cache Key Pattern | TTL | Purpose |
|---|---|---|
| `pred:{season}:{teamA}:{teamB}` | 24h (pre-tourney), 1h (during) | Model predictions |
| `analysis:{teamA}:{teamB}` | 2h (pre-tourney), 30m (during) | Claude analyses |
| `expert:{teamA}:{teamB}` | 2h (pre-tourney), 30m (during) | Web search results |
| `chat:{session_id}` | 1h | Chat conversation history |
| `ratelimit:{user_id}:{feature}` | 24h | Per-user rate limiting |
| `conf_strength:{season}:{conf}` | 24h | Conference metrics |
| `monte_carlo:{bracket_hash}` | 1h | Simulation results |

**Claude API (GenAI Layer)**
- Anthropic handles scaling on their end (default 1000 req/min Tier 2)
- **Spike handling strategies:**
  - Pre-generate all Round 1 analyses via Batch API (50% discount)
  - Aggressive Redis caching — most users ask about same matchups
  - Haiku fallback when Sonnet queue depth is high
  - Client-side debouncing — don't fire API calls on every click
  - Circuit breaker: if Claude errors spike, serve cached analyses + fallback message

**Why proxy Claude through FastAPI (not called from frontend):**
- API key stays server-side (security)
- Server-side caching of analyses in Redis (cost savings)
- Rate limiting per user (prevent abuse)
- Inject model predictions into Claude context (backend knows model outputs)
- Log usage for cost monitoring

### Cost at Scale

| Component | Free Tier | Est. Cost (10K DAU peak) |
|---|---|---|
| Vercel (frontend) | 100GB bandwidth | $20/mo Pro |
| Fly.io (backend) | 3 shared VMs | $30-60/mo |
| Neon (Postgres) | 0.5 GB storage | $19/mo Launch |
| Upstash (Redis) | 10K cmds/day | $10-30/mo |
| Claude API (GenAI) | — | $500-800/mo (w/ caching) |
| **Total** | | **~$600-930/mo peak** |

For the 3-week tournament: approximately **$450-700** total including GenAI. Pre- and post-tournament drops to ~$20/mo. Keeps running as a portfolio piece for pennies.

### Scaling Playbook

**Normal (pre-tournament):** 1 Fly.io machine, free tiers everywhere. ~$0-20/mo.

**Selection Sunday spike:** Fly.io auto-scales to 3-5 machines. Pre-generated analyses from Redis. Vercel CDN absorbs frontend load.

**Sustained tournament:** Fly.io stabilizes at 2-3 machines. New round = cache miss burst → Claude calls spike then settle. After Round 1, only 32 teams remain → cache hit rate improves dramatically.

**Post-tournament:** Everything scales to zero/minimum. Portfolio mode for pennies.

---

## Timeline (Aligned with Kaggle deadlines)

### Week 1 (Now → Mar 3): Foundation + First Submission
- [x] EDA notebooks — understand data shape
- [ ] Conference strength pipeline (`compute_conference_strength.py`)
- [ ] Feature engineering pipeline (Elo, conf strength, box scores, seeds)
- [ ] **Baseline model + FIRST Kaggle submission** (Elo-only, get on Stage 1 leaderboard)
- [ ] FastAPI skeleton with /predictions and /teams endpoints
- [ ] Next.js project scaffold + landing page
- [ ] Set up Neon Postgres + Upstash Redis

### Week 2 (Mar 3 → Mar 10): Full Model + GenAI + Second Submission
- [ ] Full feature set (Massey ordinals, momentum, coach, geography)
- [ ] XGBoost + LightGBM training + Optuna tuning
- [ ] Platt scaling / isotonic calibration on outputs
- [ ] **Second Kaggle submission** (full features, check Stage 1 leaderboard improvement)
- [ ] Claude integration: matchup analysis + expert takes
- [ ] Bracket visualization component with AI analysis panel
- [ ] Dashboard with team rankings + conference strength table
- [ ] Head-to-head comparison page

### Week 3 (Mar 10 → Mar 17): Chat Agent + Deploy + Third Submission
- [ ] Bracket Chat Agent (backend context builder + frontend UI)
- [ ] Ensemble tuning on historical Brier score
- [ ] **Third Kaggle submission** (ensemble, compare to Stage 1 leaderboard)
- [ ] Monte Carlo bracket simulation
- [ ] Team profile pages with conference context
- [ ] Deploy to Fly.io + Vercel (scalable infra)
- [ ] Load testing: simulate Selection Sunday traffic spike
- [ ] Pre-generate Round 1 analyses via Batch API (50% discount)
- [ ] Mobile responsiveness

### Week 4 (Mar 17 → Mar 19): Retrain + Final Submission + Go Live
- [ ] **~Mar 15: Kaggle releases updated data** (includes conf tourney results)
- [ ] **Mar 15: Selection Sunday** — actual seeds revealed
- [ ] Retrain model on updated data + incorporate actual seeds
- [ ] Check for injuries / suspensions via web search → manual adjustments
- [ ] **Final Kaggle submissions** (aim for 2-3 submissions to choose from)
- [ ] **SELECT 2 SUBMISSIONS** before Mar 19 4PM UTC:
  - One "safe" (well-calibrated ensemble)
  - One "bold" (slightly more aggressive on upsets)
- [ ] Update web app predictions from retrained model
- [ ] Invalidate Redis caches, regenerate analyses for actual bracket
- [ ] README + demo video for portfolio
- [ ] Monitor live traffic + GenAI costs

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Men's + Women's | Separate models | Different competitive dynamics, pace, conference structures |
| Prediction format | All pairwise (all D1 teams) | Required by Kaggle 2026 format |
| Calibration | Isotonic regression post-hoc | Brier score punishes overconfidence; calibration > raw accuracy |
| Prediction clipping | [0.02, 0.98] | Never predict certainty — Brier severely penalizes confident misses |
| Submission strategy | 2 selected: 1 safe + 1 bold | Hedges between consistency and upside |
| GenAI model | Sonnet 4.5 (analysis/chat), Haiku 4.5 (summaries) | Cost/quality balance |
| Claude API routing | Proxied through FastAPI | Security, caching, rate limiting, context injection |
| Real-time updates | SSE for chat streaming, polling for predictions | SSE gives chat a real-time feel |
| Backend hosting | Fly.io with auto-scaling | Handles Selection Sunday / Round 1 spikes (1→10 machines) |
| Model serving | Pickled model loaded at startup | Simple, fast, ~5MB, no MLOps overhead |
| Database | Neon serverless Postgres | Scales to zero when idle, PgBouncer built-in |
| Caching | Upstash Redis (serverless) | Pay-per-request, multi-layer TTL strategy |
| Conference strength | Multi-metric (Elo avg, depth, non-conf WR, Massey) | Ensemble of signals is more robust than any single metric |
| Frontend hosting | Vercel with ISG | Auto-scales, CDN, edge functions — handles traffic spikes natively |

---

## Portfolio Impact

This project demonstrates:
- **ML Engineering**: Feature engineering (inc. conference strength), ensembles, calibration, SHAP explainability
- **GenAI / AI Engineering**: Claude API, prompt engineering, web search, context injection, streaming, cost optimization
- **Full-Stack Development**: React, FastAPI, REST APIs, SSE streaming, database design
- **Data Engineering**: ETL from raw CSVs → processed features → model → API → UI
- **Scalability & Infrastructure**: Auto-scaling backend, multi-layer caching, serverless databases, load testing, circuit breakers
- **Product Thinking**: Chat agent is a genuine product innovation; "model vs experts" is shareable content
- **Cost Engineering**: Prompt caching, model tiering, Redis caching, rate limiting, Batch API pre-generation
- **Competition Strategy**: Calibration-first approach, Stage 1 validation, retrain-on-update pipeline, dual-submission hedging

**Interview talking points:**
- "I built an ML model predicting March Madness outcomes with a 0.187 Brier score, then wrapped it in a production web app with a Claude-powered chat agent that helps users build their brackets"
- "The GenAI layer explains model predictions in natural language and uses web search to synthesize expert opinions — but the LLM never overrides the ML model"
- "I engineered conference strength as a multi-dimensional feature using Elo averages, non-conference win rates, and Massey ordinal rankings — it improved Brier score by X%"
- "The app auto-scales from 1 machine to 10 on Fly.io to handle Selection Sunday traffic spikes, with a multi-layer Redis cache that keeps GenAI costs under $X for the tournament"
- "I used isotonic calibration and prediction clipping to optimize for Brier score rather than raw accuracy — calibration matters more than being right"

Perfect talking point for the Félix Pago interview — shows you can take ML from notebook to scalable production AI product.

---

## Brand Quick Reference

| Element | Value |
|---|---|
| **Name** | Ubunifu Madness |
| **Tagline** | AI-Powered March Madness Predictions |
| **URL** (target) | ubunifumadness.com |
| **GitHub repo** | ubunifu-madness |
| **Color palette** | Deep navy (#0c1222), Ember orange (#f97316), Electric blue (#3b82f6), Signal green (#22c55e) |
| **Typography** | Space Grotesk (headings), JetBrains Mono (data/stats) |
| **Logo mark** | UM monogram |
| **Voice** | Bold, opinionated, data-backed. "The model says..." not "We think..." |
