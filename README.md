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
        string game_type "regular/tourney"
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
│   │   ├── models/                 # 9 ORM models
│   │   ├── routers/                # 7 API routers (~30 endpoints)
│   │   │   ├── teams.py            # Team search & details
│   │   │   ├── rankings.py         # Power & conference rankings
│   │   │   ├── predictions.py      # Head-to-head predictions
│   │   │   ├── compare.py          # Team comparison with stats
│   │   │   ├── bracket.py          # Tournament bracket & simulation
│   │   │   ├── chat.py             # AI Madness Agent (SSE streaming)
│   │   │   └── espn.py             # Live ESPN data + admin endpoints
│   │   ├── services/
│   │   │   └── espn.py             # ESPN API client with TTL cache
│   │   └── genai/                  # Claude AI prompt engineering
│   ├── scripts/
│   │   ├── compute_stats.py        # Elo + conference strength + team stats
│   │   ├── update_elo_live.py      # Live Elo updates from ESPN results
│   │   ├── cron_elo_update.py      # Daily cron wrapper (M+W)
│   │   ├── load_predictions.py     # Load predictions CSV into DB
│   │   └── espn_team_mapper.py     # Map Kaggle ↔ ESPN team IDs
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router pages
│   │   │   ├── page.tsx            # Home
│   │   │   ├── dashboard/          # Power & conference rankings
│   │   │   ├── scores/             # Live ESPN scores with auto-refresh
│   │   │   ├── bracket/            # Tournament bracket viewer
│   │   │   ├── compare/            # Head-to-head team comparison
│   │   │   ├── chat/               # AI Madness Agent
│   │   │   └── team/[id]/          # Team detail page
│   │   ├── components/             # Shared UI components
│   │   └── lib/                    # Types & utilities
│   └── package.json
├── notebooks/
│   └── Ubunifu_Madness_March_ML_Mania.ipynb
├── data/
│   ├── raw/                        # Kaggle CSVs (not in git)
│   └── espn_team_map.json          # ESPN ↔ Kaggle ID mapping
└── docs/
    ├── MODEL.md                    # ML pipeline deep-dive
    ├── RETRAINING.md               # Step-by-step retraining guide
    ├── API.md                      # Full API reference
    └── ROADMAP.md                  # Enhancement ideas
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
2. Compute stats: `cd backend && python3 -m scripts.compute_stats`
3. Map ESPN teams: `python3 -m scripts.espn_team_mapper`
4. Load predictions: `python3 -m scripts.load_predictions ../submissions/stage2_submission_v2.csv`

See [docs/RETRAINING.md](docs/RETRAINING.md) for the full pipeline walkthrough.

## Documentation

- **[Model Documentation](docs/MODEL.md)** — ML pipeline, feature engineering, model selection, calibration
- **[Retraining Guide](docs/RETRAINING.md)** — Step-by-step instructions for retraining with new data
- **[API Reference](docs/API.md)** — All backend endpoints with parameters and response shapes
- **[Roadmap](docs/ROADMAP.md)** — Enhancement ideas and future work

## Key Features

- **Power Rankings** — Custom Elo-based rankings for 700+ teams (men's and women's), updated daily from ESPN results
- **Live Scores** — Real-time ESPN scoreboard with Elo enrichment and model win probabilities, auto-refreshing every 30s
- **Tournament Bracket** — Full bracket visualization with model-predicted advancement probabilities via Monte Carlo simulation
- **Team Comparison** — Side-by-side statistical breakdown (Four Factors, efficiency, momentum, coaching) with head-to-head win probability
- **Madness Agent** — AI-powered chat assistant (Claude) with full access to team data, Elo ratings, and predictions for bracket analysis
- **Automated Elo Updates** — Daily cron job fetches ESPN game results and updates Elo ratings, conference strength, and team records

## Model Performance

| Metric | Value |
|--------|-------|
| Brier Score (calibrated) | **0.1607** |
| Ensemble | LR (76%) + LightGBM (24%) |
| Features | 27 across 7 categories |
| Calibration | Isotonic regression |
| CV Strategy | Leave-one-season-out (2015-2025) |

See [docs/MODEL.md](docs/MODEL.md) for the full breakdown.
