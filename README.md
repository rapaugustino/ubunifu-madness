# Ubunifu Madness

AI-powered March Madness prediction platform that combines custom Elo ratings, advanced statistical modeling, and live ESPN data to predict NCAA basketball tournament outcomes.

Built for the [Kaggle March Machine Learning Mania 2025](https://www.kaggle.com/competitions/march-machine-learning-mania-2025) competition — and extended into a full-stack web application with live scores, power rankings, bracket visualization, and an AI analysis agent.

## Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend (Next.js + Tailwind)"]
        HP[Home Page]
        DB[Dashboard / Rankings]
        SC[Live Scores]
        BR[Bracket Viewer]
        CP[Compare Tool]
        CH[Madness Agent Chat]
    end

    subgraph Backend["Backend (FastAPI)"]
        API[API Layer - /api/*]
        SVC[ESPN Service]
        AI[GenAI / Claude]
        MODELS[SQLAlchemy Models]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL on Railway)]
        ESPN[ESPN API]
        KAG[Kaggle CSVs]
    end

    subgraph ML["ML Pipeline"]
        NB[Jupyter Notebook]
        CS[compute_stats.py]
        ELO[Live Elo Updater]
    end

    Frontend -->|HTTP/SSE| API
    API --> SVC
    API --> AI
    API --> MODELS
    SVC --> ESPN
    MODELS --> PG
    CS -->|Elo, conf strength, stats| PG
    NB -->|Predictions CSV| PG
    ELO -->|Daily updates| PG
    KAG -->|Historical data| CS
    KAG -->|Training data| NB
```

## Database Schema

```mermaid
erDiagram
    Team {
        int id PK
        string name
        string gender "M or W"
        int first_d1_season
        int last_d1_season
        int espn_id
        string logo_url
        string color
    }

    EloRating {
        int id PK
        int season
        int team_id FK
        float elo
        int snapshot_day "154 = end of season"
    }

    GameResult {
        int id PK
        int season
        int day_num
        int w_team_id FK
        int w_score
        int l_team_id FK
        int l_score
        string w_loc "H/A/N"
        int num_ot
        string game_type "regular/conf_tourney/tourney"
        string gender
    }

    Prediction {
        int id PK
        int season
        int team_a_id FK "lower ID"
        int team_b_id FK "higher ID"
        float win_prob_a
        string model_version
        string gender
    }

    TourneySeed {
        int id PK
        int season
        int team_id FK
        string seed "e.g. W01"
        int seed_number "1-16"
        string region
    }

    TeamSeasonStats {
        int id PK
        int season
        int team_id FK
        int wins
        int losses
        float win_pct
        float sos "avg opponent Elo"
        float avg_efg_pct
        float avg_to_pct
        float avg_or_pct
        float avg_ft_rate
        float avg_off_eff
        float avg_def_eff
        float avg_tempo
        float massey_avg_rank
        string coach_name
    }

    GamePrediction {
        int id PK
        int espn_game_id UK
        string gender
        float prob_away
        float prob_home
        string source "blended/live_blend"
        datetime locked_at
        boolean resolved
        boolean correct
    }

    Player {
        int id PK
        int espn_id UK
        int team_id FK
        string name
        string position
        int jersey
        string gender
    }

    PlayerSeasonStats {
        int id PK
        int season
        int player_id FK
        int games_played
        float ppg
        float rpg
        float apg
        float spg
        float bpg
        float fgp
        float tpp
        float ftp
        float mpg
    }

    Conference {
        string abbrev PK
        string description
    }

    TeamConference {
        int id PK
        int season
        int team_id FK
        string conf_abbrev FK
    }

    ConferenceStrength {
        int id PK
        int season
        string gender
        string conf_abbrev FK
        float avg_elo
        float elo_depth
        float top5_elo
        float nc_winrate
        float tourney_hist_winrate
    }

    Team ||--o{ EloRating : has
    Team ||--o{ TeamSeasonStats : has
    Team ||--o{ TourneySeed : seeded_in
    Team ||--o{ TeamConference : belongs_to
    Team ||--o{ Prediction : "team_a or team_b"
    Team ||--o{ GameResult : "winner or loser"
    Team ||--o{ Player : has
    Player ||--o{ PlayerSeasonStats : has
    Conference ||--o{ TeamConference : contains
    Conference ||--o{ ConferenceStrength : measured_by
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, TypeScript |
| Backend | FastAPI, SQLAlchemy 2, Pydantic |
| Database | PostgreSQL (Railway) |
| ML | scikit-learn, LightGBM, Optuna, pandas, NumPy |
| AI Agent | Anthropic Claude (streaming SSE) |
| Live Data | ESPN API (scores, rankings, rosters, schedules) |
| Deployment | Railway (backend), Vercel (frontend) |

## Project Structure

```
ubunifu-madness/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── config.py               # Environment settings
│   │   ├── database.py             # SQLAlchemy engine & session
│   │   ├── models/                 # 11 ORM models
│   │   │   ├── team.py             # Team with ESPN mapping
│   │   │   ├── elo_rating.py       # Elo snapshots per season/day
│   │   │   ├── game_result.py      # Historical + live game results
│   │   │   ├── prediction.py       # Static model predictions
│   │   │   ├── game_prediction.py  # Locked live predictions per game
│   │   │   ├── team_stats.py       # TeamSeasonStats (record, SOS, Four Factors)
│   │   │   ├── conference.py       # Conference + TeamConference
│   │   │   ├── conference_strength.py
│   │   │   ├── tournament.py       # TourneySeed
│   │   │   ├── player.py           # Player + PlayerSeasonStats
│   │   │   └── model_artifact.py   # Stored model metadata
│   │   ├── routers/                # 9 API routers
│   │   │   ├── teams.py            # Team search & details
│   │   │   ├── rankings.py         # Power & conference rankings
│   │   │   ├── predictions.py      # Head-to-head predictions
│   │   │   ├── compare.py          # Team comparison with stats
│   │   │   ├── bracket.py          # Tournament bracket & simulation
│   │   │   ├── chat.py             # AI Madness Agent (SSE streaming)
│   │   │   ├── espn.py             # Live ESPN data + admin endpoints
│   │   │   ├── players.py          # Player search & stats
│   │   │   └── performance.py      # Model accuracy tracking
│   │   └── services/
│   │       ├── espn.py             # ESPN API client with TTL cache
│   │       ├── predictor.py        # Blended 6-signal predictor
│   │       └── player_sync.py      # ESPN → DB player/stat sync
│   ├── scripts/
│   │   ├── compute_stats.py        # Elo + conference strength + team stats
│   │   ├── update_elo_live.py      # Live Elo updates from ESPN results
│   │   ├── cron_elo_update.py      # Daily cron wrapper (M+W)
│   │   ├── import_predictions.py   # Load predictions CSV into DB
│   │   ├── map_espn_ids.py         # Map Kaggle ↔ ESPN team IDs
│   │   ├── seed_db.py              # Initial database seeding from CSVs
│   │   ├── update_detailed_stats.py # Refresh Four Factors from Kaggle
│   │   └── backfill_espn_games.py  # Backfill missing ESPN game results
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router pages
│   │   │   ├── page.tsx            # Home
│   │   │   ├── dashboard/          # Power & conference rankings
│   │   │   ├── scores/             # Live ESPN scores with auto-refresh
│   │   │   ├── scores/[gameId]/    # Game detail with box score
│   │   │   ├── teams/              # Team directory
│   │   │   ├── teams/[id]/         # Team detail page
│   │   │   ├── compare/            # Head-to-head team comparison
│   │   │   ├── bracket/            # Tournament bracket viewer
│   │   │   ├── chat/               # AI Madness Agent
│   │   │   ├── performance/        # Model accuracy tracking
│   │   │   ├── about/              # Methodology documentation
│   │   │   └── terms/              # Terms & disclaimers
│   │   └── components/             # Shared UI components
│   └── package.json
├── notebooks/
│   └── Ubunifu_Madness_March_ML_Mania.ipynb
└── data/
    ├── raw/                        # Kaggle CSVs (not in git)
    └── espn_team_map.json          # ESPN ↔ Kaggle ID mapping
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (or a Railway database URL)

### Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and ANTHROPIC_API_KEY

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure API URL
# Create .env.local with:
# NEXT_PUBLIC_API_URL=http://localhost:8000

# Run dev server
npm run dev
```

The app is now available at `http://localhost:3000`.

### Data Pipeline (First-Time Setup)

1. Download Kaggle data: [March Machine Learning Mania 2025](https://www.kaggle.com/competitions/march-machine-learning-mania-2025/data) — place CSVs in `data/raw/`
2. Seed database: `cd backend && python3 -m scripts.seed_db`
3. Compute stats: `python3 -m scripts.compute_stats`
4. Map ESPN teams: `python3 -m scripts.map_espn_ids`
5. Load predictions: `python3 -m scripts.import_predictions ../submissions/stage2_submission_v2.csv`

## Key Features

- **Power Rankings** — Custom Elo-based rankings for 700+ teams (men's and women's), updated daily from ESPN results
- **Live Scores** — Real-time ESPN scoreboard with Elo enrichment and blended win probabilities, locked before tipoff with post-game accuracy tracking
- **Blended Predictions** — 6-signal prediction system: Static Model (30%), Elo (30%), Momentum (15%), Conference Strength (10%), SOS-Adjusted Record (10%), Efficiency (5%)
- **Tournament Bracket** — Full bracket visualization with model-predicted advancement probabilities via Monte Carlo simulation
- **Team Comparison** — Side-by-side statistical breakdown (Four Factors, efficiency, momentum, coaching) with head-to-head win probability
- **Madness Agent** — AI-powered chat assistant (Claude) with 6 tools: team lookup, blended matchup predictions, conference analysis, rankings, live scores, upset finder
- **Performance Tracking** — Cumulative accuracy charts, daily breakdowns, calibration curves, and paginated game log. Predictions locked before tipoff, never changed retroactively.
- **Tossup Handling** — Games with <52% model confidence labeled as TOSSUP, excluded from accuracy metrics
- **Automated Daily Pipeline** — Cron job updates Elo ratings, game results, team records, player stats, strength of schedule, and conference strength

## Model Performance

| Metric | Value |
|--------|-------|
| Brier Score (calibrated) | **0.1413** |
| Static Ensemble | LR (76%) + LightGBM (24%) |
| Features | 31 across 8 categories |
| Calibration | Isotonic regression |
| CV Strategy | Leave-one-season-out (2015-2025) |
| Live Prediction | Blended 6-signal (Elo + Model + Momentum + Conference + SOS + Efficiency) |

See [docs/MODEL.md](docs/MODEL.md) for the full breakdown.
