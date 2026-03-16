# Roadmap

Enhancement ideas organized by impact and effort. Focused on: accurate predictions, data integrity, great UX, and filling the gap left by 538's shutdown.

---

## Completed

- Elo rating system with Optuna-tuned parameters (K=21.8, HOME_ADV=101.9)
- V6 LR + LightGBM ensemble model (Val Brier: 0.139, 79.6% accuracy, 165,640 recency-weighted training games)
- 43-feature pipeline with smooth isotonic calibration
- Live ESPN scores integration with background refresh
- AI Madness Agent chat with streaming responses and 6 tools
- Interactive bracket visualization
- Head-to-head team comparison tool
- Power rankings with conference strength (Avg Elo, NC Win %, Top 5 Elo, Parity)
- Automated daily Elo updates from ESPN
- Rate-limited chat endpoint
- Team logos and colors via ESPN mapping
- Men's and women's basketball coverage across all features
- Full-roster team rankings with pagination (all D1 teams)
- Methodology / How It Works page with transparent documentation
- Terms, disclaimers, and data attribution
- **V6 ML ensemble** — 43-feature LR+LGB model with recency-weighted training (5-season half-life), home court adjusted AdjEM, and feature-diff based explanations
- **Live prediction recomputation** — predictions built from live DB state (Elo, efficiency, rankings, quality wins)
- **Tossup handling** — games with <55% confidence labeled as TOSSUP
- **Strength of schedule (SOS)** — computed live from all season game results, refreshed daily
- **Performance tracking page** — cumulative accuracy charts, daily breakdowns, calibration curves, paginated game log
- **Locked predictions** — every prediction frozen before tipoff, never changed retroactively
- **Conference strength as prediction signal** — avg Elo probability + NC win rate differential blended into predictions
- **Conference standings from ESPN** — within-conference rankings (seed, conf record, home/away splits, streak, PPG) for both M and W, refreshed daily via cron
- **Conf tourney confidence compression** — 0.85 post-calibration compression for conf tourney predictions, fixing 70-75% band from +11% overconfident to near-perfect
- **Comprehensive chat agent** — blended matchup predictions, live scores, tossup awareness, SOS and conference knowledge
- **Advanced analytics dashboard** — KenPom-depth metrics (AdjOE/AdjDE/AdjEM, Barthag, luck, floor/ceiling, upset vulnerability) computed from game data and displayed in sortable, expandable power rankings

---

## High Impact, Medium Effort

### ~~Live Prediction Recomputation~~ ✓ DONE
Implemented via the ML ensemble. Predictions use 43 features built from live DB state — Elo, adjusted efficiency, quality wins, game context, rankings, and more. The model builds features fresh for every matchup from the database.

### Player Impact Modeling
Injuries and transfers are the biggest blind spot. A star player being out can swing a game 5-10 points.

- Integrate ESPN injury reports (available via their API)
- Build player importance scores (minutes played, usage rate)
- Adjust team strength when key players are out
- Even a simple "key player missing → lower team Elo by X" would help

### Bracket Simulation Engine
Run thousands of bracket simulations like BartTorvik's TourneyCast.

- Monte Carlo simulation (10,000 runs)
- Show probability distributions for each team reaching each round
- Championship probability leaderboard
- "What if" seed swaps — users change seeds, see how probabilities shift

### Upset Radar with Explanations
Not just flagging upsets, but explaining WHY — like 538 used to do.

- Flag games where lower-seeded team has >40% win probability
- Auto-generate natural language explanations: "Team A's 3PT shooting (47%) vs Team B's perimeter defense (ranked #290) creates a mismatch"
- Show which features are pushing the probability toward the upset
- "Upset Watch" badges on scores page during the tournament

---

## High Impact, Low Effort

### Mobile Responsiveness
The app works on desktop but several pages need mobile optimization.

- Bracket page: horizontal scroll or accordion layout for mobile
- Compare page: stack teams vertically on small screens
- Dashboard table: responsive column hiding (already started)

### ~~Recency-Weighted Rankings~~ ✓ DONE (V5)
V5 model uses exponential decay with 5-season half-life for training weights. Recent games emphasized ~7x more than oldest training data.

### Recency-Weighted Within-Season Rankings
BartTorvik weights recent games more within a single season. Could add in-season decay for AdjEM computation.

- Decay weight for games older than 40 days within the current season
- Show "Recent Form" as a separate ranking alongside season-long Elo
- Let users toggle between "Season" and "Last 30 Days" views

### Historical Pattern Matching
"Teams with this statistical profile have gone X rounds deep Y% of the time."

- Match current team profiles to historical tournament analogs
- Show which past teams are most similar (Elo, Four Factors, seed)
- Surface Cinderella patterns (mid-major teams that overperformed their seed)

### Kaggle Submission Automation
Streamline the competition workflow.

- One-click script to generate and submit predictions
- Auto-log Kaggle leaderboard scores
- Compare model versions side-by-side
- Stage 1 → Stage 2 diff report

---

## Medium Impact, Medium Effort

### User Accounts and Saved Brackets
Let users create and track their own brackets.

- Auth via OAuth (Google, GitHub)
- Save bracket picks, track performance during tournament
- Leaderboard comparing users' bracket accuracy
- Bracket comparison tool: user picks vs model picks

### Conference Tournament Coverage
Dedicated tracking during conference tournament season (early March).

- Automatic bubble watch (teams on the edge of tournament selection)
- Conference tournament brackets with predictions
- Impact analysis ("if team X wins their conf tournament, they get in")

### Real-Time In-Game Win Probability
During live games, update win probabilities based on current score and time remaining.

- ESPN provides live score data every 30 seconds
- Log5 model with score differential, time remaining, and pregame Elo
- Live win probability graphs on the scores page
- Excitement Index (average win probability swing per possession)

### Box Score Feature Updates from ESPN
Currently Four Factors come from Kaggle CSVs (end-of-season). ESPN has real-time box score data.

- Parse box scores from ESPN game summaries
- Update team season stats (eFG%, TO%, ORB%, FTR) after each game
- Makes statistical features as fresh as Elo ratings

---

## Medium Impact, Low Effort

### API Public Tier
Open the API for external developers.

- API key management
- Rate limiting per key
- OpenAPI/Swagger documentation (FastAPI auto-generates this)

### SEO and Social Sharing
Make team and matchup pages shareable.

- Open Graph meta tags for team pages
- Dynamic social preview images for matchup predictions
- Structured data for search engines

### Push Notifications
Alert users during the tournament.

- Upset alerts when model-predicted upsets are in progress
- Game start reminders
- Web push notifications (no app needed)

---

## Future Architecture

### Model Ensemble Expansion
- Neural network with entity embeddings for teams
- Bayesian approaches with uncertainty estimates
- Temporal models that weight recent seasons more heavily

### Data Pipeline Automation
- GitHub Actions workflow triggered by new Kaggle data
- Automated model retraining and evaluation
- Canary deployment (compare new model vs current before switching)

### Multi-Year Backtesting Dashboard
- Year-by-year Brier score comparison vs seed baseline
- Calibration plots per season
- Biggest misses and correct upset predictions
- Communicates model credibility

---

## Removed

- ~~Betting Line Integration~~ — Removed. Platform is analytics-only, not gambling-adjacent.
- ~~Dark Mode toggle~~ — Already dark-first. Light mode is low priority.
