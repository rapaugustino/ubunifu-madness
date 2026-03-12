# API Reference

Base URL: `/api` (all endpoints are prefixed with `/api`)

Health check: `GET /health` — returns `{"status": "ok"}`

---

## Teams

### `GET /teams`

List teams with filtering and pagination.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"all"` | Filter by gender: `M`, `W`, or `all` |
| `season` | int | 2026 | Season year |
| `search` | string | — | Search by team name |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "teams": [
    {
      "id": 1242,
      "name": "Michigan",
      "gender": "M",
      "seed": 2,
      "conference": "Big Ten",
      "elo": 2095.6,
      "record": "28-5",
      "winPct": 0.848,
      "logo": "https://a.espncdn.com/...",
      "color": "#00274C"
    }
  ],
  "total": 355
}
```

### `GET /teams/{team_id}`

Get full team details including stats, conference context.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | 2026 | Season year |

**Response:** Team object with nested `stats` (Four Factors, efficiency, momentum, coach) and `conferenceContext` (avg_elo, depth, winrates).

---

## Rankings

### `GET /rankings/power`

Power rankings sorted by Elo rating.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |
| `season` | int | 2026 | Season year |
| `limit` | int | 50 | Results per page |
| `offset` | int | 0 | Pagination offset |

**Response:**
```json
{
  "rankings": [
    {
      "rank": 1,
      "team": {
        "id": 1242,
        "name": "Michigan",
        "gender": "M",
        "seed": 2,
        "conference": "Big Ten",
        "elo": 2095.6,
        "record": "28-5",
        "winPct": 0.848,
        "logo": "https://a.espncdn.com/...",
        "color": "#00274C"
      },
      "elo": 2095.6,
      "record": "28-5",
      "conference": "Big Ten",
      "confStrength": 1620.5,
      "trend": "up",
      "trendAmount": 12.3,
      "adjOE": 118.4,
      "adjDE": 92.1,
      "adjEM": 26.3,
      "barthag": 0.972,
      "luck": 0.023,
      "trueShooting": 0.582,
      "oppTrueShooting": 0.478,
      "threePtRate": 0.384,
      "astToRatio": 1.45,
      "drbPct": 0.743,
      "stlPct": 0.098,
      "blkPct": 0.112,
      "marginStdev": 11.2,
      "floorEff": -3.5,
      "ceilingEff": 32.1,
      "upsetVulnerability": 18.4,
      "closeRecord": "5-2",
      "closeWinPct": 0.714,
      "pythWinPct": 0.871,
      "tempo": 68.3,
      "sos": 1587.2
    }
  ],
  "total": 355
}
```

### `GET /rankings/conferences`

Conference rankings by strength metrics.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |
| `season` | int | 2026 | Season year |

**Response:**
```json
{
  "conferences": [
    {
      "rank": 1,
      "abbrev": "big_ten",
      "name": "Big Ten",
      "avgElo": 1620.5,
      "depth": 85.3,
      "top5Elo": 1890.2,
      "ncWinrate": 0.62,
      "tourneyHistWinrate": 0.55,
      "teamCount": 18
    }
  ]
}
```

---

## Predictions

### `GET /predictions/{team_a_id}/{team_b_id}`

Get head-to-head win probability.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | 2026 | Season year |

**Response:**
```json
{
  "season": 2026,
  "teamA": { "id": 1242, "name": "Michigan" },
  "teamB": { "id": 1211, "name": "Illinois" },
  "winProbA": 0.634,
  "winProbB": 0.366,
  "modelVersion": "v2"
}
```

---

## Compare

### `GET /compare/{team_a_id}/{team_b_id}`

Detailed team comparison with stats breakdown and prediction.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | 2026 | Season year |

**Response:**
```json
{
  "teamA": { "id": 1242, "name": "Michigan", "elo": 2095.6, "stats": {...}, "conferenceContext": {...} },
  "teamB": { "id": 1211, "name": "Illinois", "elo": 2022.5, "stats": {...}, "conferenceContext": {...} },
  "winProbA": 0.634,
  "winProbB": 0.366,
  "featureComparison": [
    { "label": "Offensive Efficiency", "teamA": 112.5, "teamB": 108.3, "unit": "pts/100", "lowerBetter": false },
    { "label": "Defensive Efficiency", "teamA": 95.2, "teamB": 97.1, "unit": "pts/100", "lowerBetter": true }
  ]
}
```

---

## Bracket

### `GET /bracket/full`

Complete tournament bracket with all rounds and results.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |
| `season` | int | 0 | Season (0 = auto-detect latest) |

**Response:**
```json
{
  "season": 2025,
  "gender": "M",
  "hasBracket": true,
  "isComplete": true,
  "regions": {
    "W": { "name": "West", "matchups": [...] },
    "X": { "name": "East", "matchups": [...] },
    "Y": { "name": "South", "matchups": [...] },
    "Z": { "name": "Midwest", "matchups": [...] }
  },
  "finalFour": [...],
  "championship": [...],
  "champion": { "teamId": 1242, "teamName": "Michigan", "seed": 2 },
  "roundNames": ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]
}
```

### `GET /bracket/matchups`

First-round matchups with predictions.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |
| `season` | int | 2026 | Season year |

### `POST /bracket/simulate`

Monte Carlo bracket simulation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `season` | int | 2026 | Season year |
| `gender` | string | `"M"` | `M` or `W` |
| `num_simulations` | int | 10000 | Number of simulations |

**Response:**
```json
{
  "championProbabilities": [
    { "teamId": 1242, "teamName": "Michigan", "seed": 2, "probability": 0.142 }
  ],
  "finalFourProbabilities": [...]
}
```

---

## Chat (Madness Agent)

### `POST /chat`

Stream AI bracket analysis via Server-Sent Events.

**Request body:**
```json
{
  "messages": [
    { "role": "user", "content": "Who should I pick to win it all?" }
  ],
  "gender": "M"
}
```

**Response:** `text/event-stream` (SSE) with Claude's streaming response.

**Rate limits:** 20 requests per 10 minutes, 60 per hour (per IP).

---

## ESPN (Live Data)

### `GET /scores`

Today's games with Elo enrichment and win probabilities.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | string | — | Date in YYYYMMDD format (default: today) |
| `gender` | string | `"M"` | `M` or `W` |

**Response:**
```json
{
  "games": [
    {
      "id": "401720123",
      "date": "2026-03-08T19:00Z",
      "venue": "Madison Square Garden",
      "status": "STATUS_FINAL",
      "statusDetail": "Final",
      "broadcast": "ESPN",
      "away": { "espnId": 333, "name": "Alabama", "score": 72, "kaggleId": 1104, "elo": 1890.5 },
      "home": { "espnId": 2305, "name": "Kansas", "score": 78, "kaggleId": 1242, "elo": 2095.6 },
      "winProb": { "away": 0.35, "home": 0.65 }
    }
  ]
}
```

### `GET /scores/{game_id}`

Full box score for a specific game.

### `GET /rankings/ap`

AP Top 25 enriched with Elo ratings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |

### `GET /schedule/{team_id}`

Team schedule by Kaggle team ID.

### `GET /roster/{team_id}`

Team roster with players and coach by Kaggle team ID.

---

## Admin / Maintenance Endpoints

### `POST /seeds/refresh`

Fetch tournament seeds from ESPN and upsert into DB. Call after Selection Sunday.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |
| `season` | int | 2026 | Season year |

### `POST /elo/refresh`

Update Elo ratings from ESPN game results. Idempotent.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | string | — | YYYYMMDD (default: today + yesterday) |
| `gender` | string | `"M"` | `M` or `W` |

**Response:**
```json
{
  "status": "ok",
  "gender": "M",
  "total_games_processed": 12,
  "conferences_updated": 8,
  "details": [...]
}
```

### `POST /records/refresh`

Bulk-update team win/loss records from ESPN.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gender` | string | `"M"` | `M` or `W` |
| `season` | int | 2026 | Season year |
