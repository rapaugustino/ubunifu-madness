# Roadmap

Enhancement ideas organized by impact and effort. Focused on the core goals: accurate predictions, clean code, reliable data, and a great user experience.

---

## Completed

- Elo rating system with Optuna-tuned parameters (K=21.8, HOME_ADV=101.9)
- LR + LightGBM ensemble model (Brier score: 0.1607)
- 27-feature pipeline with isotonic calibration
- Live ESPN scores integration with background refresh
- AI Madness Agent chat with streaming responses
- Interactive bracket visualization
- Head-to-head team comparison tool
- Power rankings with conference strength
- Automated daily Elo updates from ESPN
- Rate-limited chat endpoint
- Team logos and colors via ESPN mapping

---

## High Impact, Medium Effort

### Live Prediction Updates
Currently, predictions are static (computed once from the notebook). As Elo ratings update daily, predictions could be recomputed on the fly using the stored model artifacts.

- Load the LR + LGB models from `model_artifacts` table
- Recompute feature vectors with latest Elo, stats, and conference strength
- Generate fresh predictions for tournament-eligible teams
- Would make predictions more accurate as the season progresses

### Player Impact Modeling
Injuries and transfers are the biggest blind spot. A star player being out can swing a game 5-10 points.

- Integrate ESPN injury reports (available via their API)
- Build player importance scores (minutes played, usage rate, PER)
- Adjust team strength when key players are out
- Even a simple "key player missing → lower team Elo by X" would help

### Betting Line Integration
Compare model predictions vs Vegas closing lines to find value.

- Fetch odds from a public API (The Odds API has a free tier)
- Show model probability vs implied odds probability
- Highlight games where model and Vegas disagree significantly
- Useful for users who want actionable betting insights

### Advanced Analytics Page
A dedicated page for deeper statistical exploration.

- Team radar charts (Four Factors visualization)
- Elo history graphs (how a team's rating changed over the season)
- Conference strength comparison charts
- Historical tournament performance by seed

---

## High Impact, Low Effort

### Mobile Responsiveness
The app works on desktop but several pages (bracket, compare) need mobile optimization.

- Bracket page: horizontal scroll or accordion layout for mobile
- Compare page: stack teams vertically on small screens
- Dashboard table: responsive column hiding for narrow viewports

### Upset Alert System
During the tournament, highlight games where our model predicts an upset.

- Flag games where a lower-seeded team has >40% win probability
- Show "upset watch" badges on the scores page
- Useful during March Madness when users are checking constantly

### Historical Bracket Simulation
"What if" scenarios — how would the 2026 bracket play out with different seeds?

- Allow users to swap seeds and re-simulate
- Show how championship probabilities change
- Educational tool for understanding bracket dynamics

### Kaggle Submission Automation
Streamline the Kaggle competition workflow.

- One-click script to generate and submit predictions
- Auto-log Kaggle leaderboard scores for tracking improvement
- Compare model versions side-by-side (Brier score, calibration, feature importance)
- Stage 1 → Stage 2 diff report (what changed after Selection Sunday)

---

## Medium Impact, Medium Effort

### User Accounts and Saved Brackets
Let users create and track their own brackets.

- Auth via OAuth (Google, GitHub) — no passwords to manage
- Save bracket picks, track performance during tournament
- Leaderboard comparing users' bracket accuracy
- Social sharing of bracket picks

### Push Notifications
Alert users during the tournament.

- Upset alerts when model-predicted upsets are in progress
- Game start reminders for bracket-relevant matchups
- Score updates for close games
- Could use web push notifications (no app needed)

### Conference Tournament Coverage
Dedicated tracking during conference tournament season (early March).

- Automatic bubble watch (teams on the edge of tournament selection)
- Conference tournament brackets with predictions
- Impact analysis ("if team X wins their conference tournament, they get in")

---

## Medium Impact, Low Effort

### API Rate Limiting and Public Tier
The API could be opened up for external developers.

- API key management for external consumers
- Rate limiting per key (current IP-based limiting is a start)
- Documentation via OpenAPI/Swagger (FastAPI generates this automatically)
- Could attract developers building their own bracket tools

### Dark Mode / Light Mode Toggle
The app currently has a dark theme, but some elements could be refined.

- Ensure all charts and visualizations respect dark mode
- Add a light mode toggle for users who prefer it
- Test all Tooltip and modal components in both modes

### SEO and Social Sharing
Make team and matchup pages shareable.

- Open Graph meta tags for team pages
- Dynamic social preview images for matchup predictions
- Structured data for search engines

---

## Future Architecture Improvements

### Real-Time In-Game Predictions
During live games, update win probabilities based on current score, time remaining, and team strength.

- ESPN provides live score data every 30 seconds
- Simple model: log5 with score differential and time remaining
- Show live win probability graphs on the scores page

### Model Ensemble Expansion
Experiment with additional model types.

- Neural network with entity embeddings for teams
- Bayesian approaches that provide uncertainty estimates
- Temporal models that weight recent seasons more heavily

### Data Pipeline Automation
Fully automated data pipeline from Kaggle download to deployed predictions.

- GitHub Actions workflow triggered by new Kaggle data
- Automated model retraining and evaluation
- Canary deployment (compare new model vs current before switching)
- Model performance monitoring over time

### Box Score Feature Updates from ESPN
Currently Four Factors come from Kaggle CSVs (end-of-season). ESPN has box score data that could provide real-time updates.

- Parse box scores from ESPN game summaries
- Update team season stats (eFG%, TO%, ORB%, FTR) after each game
- Would make statistical features as fresh as Elo ratings

### Multi-Year Model Backtesting Dashboard
Visualize how the model would have performed across all past tournaments.

- Year-by-year Brier score comparison vs seed baseline
- Calibration plots per season
- Biggest misses and biggest wins (upsets correctly predicted)
- Helps communicate model quality to others
