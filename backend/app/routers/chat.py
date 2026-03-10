"""
Madness Agent — AI bracket advisor with tool-use.

The agent can look up any team, get matchup predictions, query conference
strength, pull top rankings, and check live scores. Claude decides which
tools to call based on the user's question, then synthesizes a grounded answer.
"""

import json
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

import anthropic

from app.config import settings
from app.db.session import get_db
from app.models import (
    Team, EloRating, TeamSeasonStats, TeamConference,
    TourneySeed, ConferenceStrength, Prediction, Conference,
)
from app.services import espn
from app.services.predictor import predict_matchup

router = APIRouter(tags=["chat"])

SEASON = 2026

# Common user abbreviations → Kaggle DB conference abbreviations
_CONF_ALIAS_MAP = {
    "B10": "big_ten", "BIG10": "big_ten", "BIG 10": "big_ten", "BIG TEN": "big_ten",
    "B12": "big_twelve", "BIG12": "big_twelve", "BIG 12": "big_twelve", "BIG TWELVE": "big_twelve",
    "BE": "big_east", "BIG EAST": "big_east",
    "PAC12": "pac_twelve", "PAC-12": "pac_twelve", "PAC 12": "pac_twelve",
    "A10": "a_ten", "A-10": "a_ten", "ATLANTIC 10": "a_ten",
    "ASUN": "a_sun", "A-SUN": "a_sun", "ATLANTIC SUN": "a_sun",
    "MOUNTAIN WEST": "mwc", "SUN BELT": "sun_belt", "SUNBELT": "sun_belt",
    "BIG SKY": "big_sky", "BIG SOUTH": "big_south", "BIG WEST": "big_west",
}

# --- Rate limiting ---
RATE_WINDOW_SHORT = 600   # 10 minutes
RATE_LIMIT_SHORT = 10
RATE_WINDOW_LONG = 3600   # 1 hour
RATE_LIMIT_LONG = 30
RATE_WINDOW_DAILY = 86400  # 24 hours
RATE_LIMIT_DAILY = 100

_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str):
    """Raise 429 if IP exceeds rate limits."""
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW_DAILY]
    timestamps = _rate_store[ip]
    recent_short = sum(1 for t in timestamps if now - t < RATE_WINDOW_SHORT)
    recent_hour = sum(1 for t in timestamps if now - t < RATE_WINDOW_LONG)
    if recent_short >= RATE_LIMIT_SHORT:
        raise HTTPException(429, f"Slow down! Max {RATE_LIMIT_SHORT} messages per {RATE_WINDOW_SHORT // 60} minutes.")
    if recent_hour >= RATE_LIMIT_LONG:
        raise HTTPException(429, f"Hourly limit reached. Max {RATE_LIMIT_LONG} messages per hour.")
    if len(timestamps) >= RATE_LIMIT_DAILY:
        raise HTTPException(429, f"Daily limit reached. Max {RATE_LIMIT_DAILY} messages per day. Come back tomorrow!")
    _rate_store[ip].append(now)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    gender: str = "M"


# ---------------------------------------------------------------------------
# Tool definitions for Claude
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "lookup_team",
        "description": (
            "Look up a college basketball team by name. Returns Elo rating, record, "
            "conference, tournament seed, and detailed season stats (Four Factors, "
            "efficiency, momentum, coach info). Use this when the user asks about a "
            "specific team."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Team name or partial name to search for (e.g. 'Duke', 'Gonzaga', 'UConn')",
                },
            },
            "required": ["team_name"],
        },
    },
    {
        "name": "get_matchup_prediction",
        "description": (
            "Get the blended 6-signal win probability prediction for a matchup between two teams. "
            "Combines Elo, static model, momentum, conference strength, SOS-adjusted record, and efficiency. "
            "Returns each team's win probability, confidence level, tossup status, and key stat comparisons. "
            "Use this when the user asks who would win, or about a specific matchup."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team_a_name": {
                    "type": "string",
                    "description": "First team name (e.g. 'Duke')",
                },
                "team_b_name": {
                    "type": "string",
                    "description": "Second team name (e.g. 'North Carolina')",
                },
            },
            "required": ["team_a_name", "team_b_name"],
        },
    },
    {
        "name": "get_conference_info",
        "description": (
            "Get conference strength metrics and the top teams in a conference. "
            "Returns average Elo, non-conference win rate, top 5 Elo, parity, and "
            "a list of teams. Use this for conference-level analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conference": {
                    "type": "string",
                    "description": "Conference abbreviation (e.g. 'SEC', 'B10', 'B12', 'ACC', 'BE') or full name",
                },
            },
            "required": ["conference"],
        },
    },
    {
        "name": "get_top_teams",
        "description": (
            "Get the top teams by Elo rating. Optionally filter by conference. "
            "Use this when the user asks about rankings, best teams, or top teams "
            "in a conference."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of teams to return (default 25, max 50)",
                },
                "conference": {
                    "type": "string",
                    "description": "Optional conference abbreviation to filter by",
                },
            },
        },
    },
    {
        "name": "get_todays_scores",
        "description": (
            "Get live scores and results from today's games (or a specific date). "
            "Shows scores, game status, and which teams are playing. "
            "Use this when the user asks about today's games or recent results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYYMMDD format (default: today)",
                },
            },
        },
    },
    {
        "name": "get_upset_candidates",
        "description": (
            "Find potential upsets — games where the lower-Elo team has a meaningful "
            "chance of winning based on our model. Use this when users ask about "
            "Cinderella picks, upsets, bracket busters, or sleeper teams."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_upset_prob": {
                    "type": "number",
                    "description": "Minimum win probability for the underdog to qualify as upset candidate (default 0.30, meaning 30%)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of upset candidates to return (default 10)",
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution functions
# ---------------------------------------------------------------------------

def _find_team(db: Session, name: str, gender: str) -> Team | None:
    """Fuzzy-find a team by name."""
    # Try exact match first
    team = db.query(Team).filter(Team.gender == gender, Team.name.ilike(name)).first()
    if team:
        return team
    # Partial match
    team = db.query(Team).filter(Team.gender == gender, Team.name.ilike(f"%{name}%")).first()
    return team


def _team_detail(db: Session, team: Team) -> dict:
    """Build full team detail dict."""
    elo = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team.id).first()
    stats = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team.id).first()
    conf = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team.id).first()
    seed = db.query(TourneySeed).filter(TourneySeed.season == SEASON, TourneySeed.team_id == team.id).first()

    conf_name = conf.conf_abbrev if conf else None
    if conf:
        cd = db.query(Conference).filter(Conference.abbrev == conf.conf_abbrev).first()
        if cd:
            conf_name = cd.description

    result = {
        "name": team.name,
        "teamId": team.id,
        "elo": round(elo.elo, 1) if elo else None,
        "record": f"{stats.wins}-{stats.losses}" if stats else None,
        "winPct": f"{stats.win_pct * 100:.1f}%" if stats else None,
        "conference": conf_name,
        "confAbbrev": conf.conf_abbrev if conf else None,
        "seed": seed.seed_number if seed else None,
    }

    if stats:
        result["stats"] = {
            "offensiveEfficiency": stats.avg_off_eff,
            "defensiveEfficiency": stats.avg_def_eff,
            "tempo": stats.avg_tempo,
            "eFG%": round(stats.avg_efg_pct * 100, 1) if stats.avg_efg_pct and stats.avg_efg_pct < 1 else stats.avg_efg_pct,
            "turnoverRate": stats.avg_to_pct,
            "offReboundRate": round(stats.avg_or_pct * 100, 1) if stats.avg_or_pct and stats.avg_or_pct < 1 else stats.avg_or_pct,
            "freeThrowRate": round(stats.avg_ft_rate * 100, 1) if stats.avg_ft_rate and stats.avg_ft_rate < 1 else stats.avg_ft_rate,
            "oppEFG%": round(stats.avg_opp_efg_pct * 100, 1) if stats.avg_opp_efg_pct and stats.avg_opp_efg_pct < 1 else stats.avg_opp_efg_pct,
            "strengthOfSchedule": round(stats.sos, 1) if stats.sos else None,
        }
        if stats.last_n_winpct is not None:
            result["momentum"] = {
                "last10WinPct": f"{stats.last_n_winpct * 100:.0f}%",
                "last10PointDiff": round(stats.last_n_mov, 1) if stats.last_n_mov else None,
            }
        if stats.coach_name:
            result["coach"] = {
                "name": stats.coach_name,
                "tenure": stats.coach_tenure,
                "tourneyAppearances": stats.coach_tourney_appearances,
                "marchMadnessWinRate": f"{stats.coach_march_winrate * 100:.0f}%" if stats.coach_march_winrate else None,
            }

    return result


def _exec_lookup_team(db: Session, gender: str, input_data: dict) -> dict:
    team = _find_team(db, input_data["team_name"], gender)
    if not team:
        return {"error": f"No team found matching '{input_data['team_name']}' in {'mens' if gender == 'M' else 'womens'} basketball."}
    return _team_detail(db, team)


def _exec_get_matchup(db: Session, gender: str, input_data: dict) -> dict:
    team_a = _find_team(db, input_data["team_a_name"], gender)
    team_b = _find_team(db, input_data["team_b_name"], gender)
    if not team_a:
        return {"error": f"Team not found: '{input_data['team_a_name']}'"}
    if not team_b:
        return {"error": f"Team not found: '{input_data['team_b_name']}'"}

    # Use the blended 6-signal predictor (team_a is "away", team_b is "home")
    prob_a, source = predict_matchup(db, team_a.id, team_b.id)

    detail_a = _team_detail(db, team_a)
    detail_b = _team_detail(db, team_b)

    confidence = max(prob_a, 1 - prob_a)
    is_tossup = confidence < 0.52

    return {
        "teamA": detail_a,
        "teamB": detail_b,
        "prediction": {
            f"{team_a.name}_winProb": f"{prob_a * 100:.1f}%",
            f"{team_b.name}_winProb": f"{(1 - prob_a) * 100:.1f}%",
            "favored": team_a.name if prob_a > 0.5 else team_b.name,
            "confidence": f"{confidence * 100:.1f}%",
            "isTossup": is_tossup,
            "source": source,
        },
    }


def _exec_get_conference(db: Session, gender: str, input_data: dict) -> dict:
    conf_input = input_data["conference"].strip()
    resolved = _CONF_ALIAS_MAP.get(conf_input.upper(), conf_input.lower())

    # Try direct abbrev match (case-insensitive)
    cs = db.query(ConferenceStrength).filter(
        ConferenceStrength.season == SEASON, ConferenceStrength.gender == gender,
        func.lower(ConferenceStrength.conf_abbrev) == resolved.lower(),
    ).first()

    # Try fuzzy match on conference description
    if not cs:
        conf_row = db.query(Conference).filter(Conference.description.ilike(f"%{input_data['conference']}%")).first()
        if conf_row:
            cs = db.query(ConferenceStrength).filter(
                ConferenceStrength.season == SEASON, ConferenceStrength.gender == gender,
                ConferenceStrength.conf_abbrev == conf_row.abbrev,
            ).first()

    if not cs:
        return {"error": f"Conference not found: '{input_data['conference']}'. Try: ACC, SEC, big_ten, big_twelve, big_east, mwc, aac."}

    # Get teams in this conference
    tc_rows = db.query(TeamConference).filter(
        TeamConference.season == SEASON, TeamConference.conf_abbrev == cs.conf_abbrev
    ).all()
    team_ids = [tc.team_id for tc in tc_rows]

    # Filter to correct gender
    teams = db.query(Team).filter(Team.id.in_(team_ids), Team.gender == gender).all()
    team_id_set = {t.id for t in teams}

    elo_map = {
        r.team_id: r.elo
        for r in db.query(EloRating).filter(
            EloRating.season == SEASON, EloRating.team_id.in_(team_id_set)
        ).all()
    }
    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats).filter(
            TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id.in_(team_id_set)
        ).all()
    }

    team_list = []
    for t in sorted(teams, key=lambda x: elo_map.get(x.id, 0), reverse=True):
        s = stats_map.get(t.id)
        team_list.append({
            "name": t.name,
            "elo": round(elo_map.get(t.id, 1500), 1),
            "record": f"{s.wins}-{s.losses}" if s else "?",
        })

    conf_desc = db.query(Conference).filter(Conference.abbrev == cs.conf_abbrev).first()

    return {
        "conference": conf_desc.description if conf_desc else cs.conf_abbrev,
        "abbrev": cs.conf_abbrev,
        "avgElo": round(cs.avg_elo, 1),
        "top5Elo": round(cs.top5_elo, 1) if cs.top5_elo else None,
        "ncWinRate": f"{(cs.nc_winrate or 0) * 100:.1f}%",
        "parity": round(cs.elo_depth, 1),
        "teams": team_list[:15],  # Cap at 15 to keep context manageable
    }


def _exec_get_top_teams(db: Session, gender: str, input_data: dict) -> dict:
    limit = min(input_data.get("limit", 25), 50)
    conf_filter = input_data.get("conference")

    query = (
        db.query(Team, EloRating)
        .join(EloRating, EloRating.team_id == Team.id)
        .filter(EloRating.season == SEASON, Team.gender == gender)
    )

    if conf_filter:
        conf_filter = _CONF_ALIAS_MAP.get(conf_filter.strip().upper(), conf_filter.strip().lower())
        conf_team_ids = [
            tc.team_id for tc in db.query(TeamConference).filter(
                TeamConference.season == SEASON,
                func.lower(TeamConference.conf_abbrev) == conf_filter.lower(),
            ).all()
        ]
        if conf_team_ids:
            query = query.filter(Team.id.in_(conf_team_ids))

    rows = query.order_by(EloRating.elo.desc()).limit(limit).all()

    team_ids = [t.id for t, _ in rows]
    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats).filter(
            TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id.in_(team_ids)
        ).all()
    }
    conf_map = {
        r.team_id: r.conf_abbrev
        for r in db.query(TeamConference).filter(
            TeamConference.season == SEASON, TeamConference.team_id.in_(team_ids)
        ).all()
    }
    seed_map = {
        r.team_id: r.seed_number
        for r in db.query(TourneySeed).filter(
            TourneySeed.season == SEASON, TourneySeed.team_id.in_(team_ids)
        ).all()
    }

    teams = []
    for i, (team, elo_row) in enumerate(rows):
        s = stats_map.get(team.id)
        teams.append({
            "rank": i + 1,
            "name": team.name,
            "elo": round(elo_row.elo, 1),
            "record": f"{s.wins}-{s.losses}" if s else "?",
            "conference": conf_map.get(team.id, "?"),
            "seed": seed_map.get(team.id),
        })

    return {"teams": teams, "gender": "Men's" if gender == "M" else "Women's"}


def _exec_get_scores(db: Session, gender: str, input_data: dict) -> dict:
    from datetime import datetime
    date_str = input_data.get("date") or datetime.now().strftime("%Y%m%d")

    try:
        games = espn.get_scoreboard(date_str, gender)
    except Exception as e:
        return {"error": f"Could not fetch scores: {str(e)}"}

    results = []
    for g in games:
        away = g.get("away", {})
        home = g.get("home", {})
        entry = {
            "away": away.get("name", "?"),
            "home": home.get("name", "?"),
            "status": g["status"],
        }
        if g["status"] == "STATUS_FINAL":
            entry["awayScore"] = away.get("score", 0)
            entry["homeScore"] = home.get("score", 0)
            entry["winner"] = away["name"] if away.get("score", 0) > home.get("score", 0) else home["name"]
        elif g["status"] != "STATUS_SCHEDULED":
            entry["awayScore"] = away.get("score", 0)
            entry["homeScore"] = home.get("score", 0)
            entry["detail"] = g.get("statusDetail", "")
        else:
            entry["tipoff"] = g.get("statusDetail", "")
        results.append(entry)

    return {
        "date": date_str,
        "gender": "Men's" if gender == "M" else "Women's",
        "totalGames": len(results),
        "games": results[:30],  # Cap to keep context reasonable
    }


def _exec_get_upset_candidates(db: Session, gender: str, input_data: dict) -> dict:
    min_prob = input_data.get("min_upset_prob", 0.30)
    limit = min(input_data.get("limit", 10), 20)

    # Get all seeded teams (tournament field)
    seeds = db.query(TourneySeed).filter(TourneySeed.season == SEASON).all()
    if not seeds:
        # Pre-tournament: find teams with big Elo gaps that are close in win prob
        # Use top 50 teams and find interesting matchups
        rows = (
            db.query(Team, EloRating)
            .join(EloRating, EloRating.team_id == Team.id)
            .filter(EloRating.season == SEASON, Team.gender == gender)
            .order_by(EloRating.elo.desc())
            .limit(50)
            .all()
        )
        if len(rows) < 2:
            return {"message": "Not enough data to find upset candidates."}

        # Find matchups where a lower-ranked team has a decent chance
        candidates = []
        elo_map = {t.id: e.elo for t, e in rows}
        stats_map = {
            r.team_id: r
            for r in db.query(TeamSeasonStats).filter(
                TeamSeasonStats.season == SEASON,
                TeamSeasonStats.team_id.in_([t.id for t, _ in rows])
            ).all()
        }
        conf_map = {
            r.team_id: r.conf_abbrev
            for r in db.query(TeamConference).filter(
                TeamConference.season == SEASON,
                TeamConference.team_id.in_([t.id for t, _ in rows])
            ).all()
        }

        top_10_ids = [t.id for t, _ in rows[:10]]
        mid_tier = [(t, e) for t, e in rows[15:50]]

        for underdog, elo_row in mid_tier:
            for fav_id in top_10_ids:
                lo, hi = min(underdog.id, fav_id), max(underdog.id, fav_id)
                pred = db.query(Prediction).filter(
                    Prediction.season == SEASON,
                    Prediction.team_a_id == lo, Prediction.team_b_id == hi,
                ).first()
                if not pred:
                    continue

                underdog_prob = pred.win_prob_a if underdog.id == lo else (1 - pred.win_prob_a)
                if underdog_prob >= min_prob:
                    fav_team = db.query(Team).get(fav_id)
                    s = stats_map.get(underdog.id)
                    candidates.append({
                        "underdog": underdog.name,
                        "underdogElo": round(elo_row.elo, 1),
                        "underdogRecord": f"{s.wins}-{s.losses}" if s else "?",
                        "underdogConf": conf_map.get(underdog.id, "?"),
                        "favorite": fav_team.name if fav_team else "?",
                        "favoriteElo": round(elo_map.get(fav_id, 1500), 1),
                        "underdogWinProb": f"{underdog_prob * 100:.1f}%",
                    })

        candidates.sort(key=lambda x: float(x["underdogWinProb"].rstrip("%")), reverse=True)
        return {"upsetCandidates": candidates[:limit], "note": "Pre-tournament analysis. Actual tournament matchups TBD after Selection Sunday."}

    # Post-selection: analyze actual seeded matchups
    return {"message": "Tournament bracket available. Use get_matchup_prediction for specific matchup analysis."}


# Tool dispatch
TOOL_DISPATCH = {
    "lookup_team": _exec_lookup_team,
    "get_matchup_prediction": _exec_get_matchup,
    "get_conference_info": _exec_get_conference,
    "get_top_teams": _exec_get_top_teams,
    "get_todays_scores": _exec_get_scores,
    "get_upset_candidates": _exec_get_upset_candidates,
}


def _execute_tool(db: Session, gender: str, tool_name: str, tool_input: dict) -> dict:
    fn = TOOL_DISPATCH.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(db, gender, tool_input)
    except Exception as e:
        return {"error": f"Tool error ({tool_name}): {str(e)}"}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Ubunifu Madness bracket advisor — an AI assistant for NCAA March Madness predictions built by Richard Pallangyo.

You have tools to look up any D1 team, get head-to-head predictions, analyze conferences, check rankings, pull live scores, and find upset candidates.

WHEN TO USE TOOLS vs. NOT:
- Use tools when the user asks about specific teams, matchups, conferences, scores, or rankings.
- Do NOT use tools for general questions like "how does the app work?", "what is Elo?", "explain your methodology", or greetings. Answer those from your knowledge below.
- For vague questions like "help me with my bracket" or "who should I pick?", ask ONE clarifying question instead of blindly calling tools. Example: "Which region or matchup are you looking at? Or would you like me to find the best upset picks?"
- Use the get_todays_scores tool whenever the user asks about live games, today's scores, or recent results. You CAN check scores — just call the tool.

ABOUT UBUNIFU MADNESS (answer from this when users ask about the app):
- Built by Richard Pallangyo for the Kaggle March ML Mania 2026 competition.

PREDICTION SYSTEM — BLENDED 6-SIGNAL MODEL:
Live predictions use a blended approach that combines 6 signals, not just the static model:
1. Static Model (30%): LR + LightGBM ensemble trained on 4,302 tournament games (1985-2025) with 31 features. Brier score 0.1413.
2. Elo (30%): Real-time Elo ratings updated daily from ESPN. K=21.8, home advantage=101.9 points. Between seasons, ratings regress 11% toward 1500.
3. Momentum (15%): Last 10 games win percentage and margin of victory. Captures hot/cold streaks.
4. Conference Strength (10%): 70% conference average Elo probability + 30% non-conference win rate differential. Accounts for quality of competition.
5. SOS-Adjusted Record (10%): Win percentage adjusted for strength of schedule. A 25-5 record against tough opponents matters more than 25-5 against weak ones. Formula: adj_wp = win_pct + (sos - 1500) / 2000.
6. Efficiency (5%): Offensive and defensive points per 100 possessions differential.

When the static model isn't available for a team, the remaining 5 signals are re-weighted (source: "live_blend"). This ensures every team gets a data-driven prediction.

TOSSUP HANDLING:
- When model confidence is below 52% (neither team favored above 52%), the game is labeled a "TOSSUP."
- Tossup games are excluded from accuracy metrics — the model is honest about when it doesn't have a strong pick.
- On the Scores page, tossups show in yellow instead of a directional pick.
- The Performance page separates "confident picks" (≥52%) from tossups.

KEY METRICS:
- Elo: Average D1 team is ~1500. Top 25 men's teams are 1800+. #1 is ~2100.
- Strength of Schedule (SOS): Average Elo of all opponents faced in the current season.
- Conference strength: Average Elo, non-conference win rate, top 5 Elo, parity.
- Prediction accuracy: Tracked on the Performance page with daily breakdowns, calibration curves, and a game-by-game log. Predictions are locked before tipoff and never changed retroactively.
- Men's and women's basketball both supported. Elo pools are independent per gender.
- No betting advice. This is for bracket strategy and analytics only.
- Data sources: Kaggle (CC BY 4.0) for historical games, ESPN for live scores. Not affiliated with NCAA or ESPN.
- For full methodology: visit the "How It Works" page.

TONE AND UNCERTAINTY:
- Sound human and conversational, not robotic. You're a knowledgeable analyst, not a spreadsheet.
- When a matchup is close (win probability between 40-60%), acknowledge the uncertainty explicitly. Say things like "this is genuinely a tossup", "I'd give a slight edge to X but I wouldn't be shocked if Y pulls it off", "the model leans X but the margin is razor-thin."
- Never be falsely confident in close games. A 52% probability is barely better than a coin flip — say so.
- For decisive matchups (>70%), be more confident but still acknowledge that upsets happen.
- Use natural hedging language: "I'd lean toward", "the numbers suggest", "if forced to pick", "there's a real case for either side."
- When discussing upset potential, frame it as opportunity: "this is the kind of game that busts brackets, but that's also what makes it exciting to pick."

Rules:
- When using tools, ground every claim in specific numbers (Elo, win probability, record, efficiency).
- Be concise and direct. Use bullet points for comparisons.
- NEVER use markdown formatting — no headers (##), no bold (**text**), no backticks (`), no italic (*text*). Use plain text only.
- Use bullet points (- ) and line breaks for structure. Use CAPS for emphasis instead of bold.
- If a tool returns an error, tell the user honestly.
- No betting advice. This is for bracket strategy only.
- When comparing teams, explain WHY one team has an edge — which specific stats matter.
- For upset picks, explain the statistical basis (e.g. "their 3PT defense is weak and the underdog shoots 38% from 3").
- Keep responses focused. 2-4 paragraphs max for data questions, shorter for general questions."""


# ---------------------------------------------------------------------------
# Chat endpoint with tool-use loop
# ---------------------------------------------------------------------------

@router.post("/chat")
def chat(req: ChatRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    _check_rate_limit(client_ip.split(",")[0].strip())

    # Build initial context with top 10 teams (lightweight overview)
    top_rows = (
        db.query(Team, EloRating)
        .join(EloRating, EloRating.team_id == Team.id)
        .filter(EloRating.season == SEASON, Team.gender == req.gender)
        .order_by(EloRating.elo.desc())
        .limit(10)
        .all()
    )
    overview = f"Quick reference — Top 10 {'Mens' if req.gender == 'M' else 'Womens'} teams by Elo:\n"
    for i, (team, elo_row) in enumerate(top_rows):
        overview += f"{i+1}. {team.name} (Elo {elo_row.elo:.0f})\n"
    overview += "\nUse your tools to look up detailed stats, matchups, and scores."

    system = f"{SYSTEM_PROMPT}\n\n{overview}"

    # Convert incoming messages
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate():
        current_messages = list(messages)
        max_tool_rounds = 3

        for _ in range(max_tool_rounds):
            # Non-streaming call that may include tool use
            response = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1024,
                system=system,
                messages=current_messages,
                tools=TOOLS,
            )

            # Check for tool use
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if not tool_blocks:
                # No more tool calls — send final text
                for b in text_blocks:
                    yield f"data: {json.dumps({'text': b.text})}\n\n"
                yield "data: [DONE]\n\n"
                return

            # Execute tools and continue the loop
            # Serialize assistant's response (including tool_use blocks)
            assistant_content = []
            for b in response.content:
                if b.type == "text":
                    assistant_content.append({"type": "text", "text": b.text})
                elif b.type == "tool_use":
                    assistant_content.append({
                        "type": "tool_use",
                        "id": b.id,
                        "name": b.name,
                        "input": b.input,
                    })

            current_messages.append({"role": "assistant", "content": assistant_content})

            # Execute each tool and build results
            tool_results = []
            for tb in tool_blocks:
                result = _execute_tool(db, req.gender, tb.name, tb.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": json.dumps(result, default=str),
                })

            current_messages.append({"role": "user", "content": tool_results})

        # Exhausted tool rounds — do one final call without tools
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            messages=current_messages,
        )
        for b in response.content:
            if b.type == "text":
                yield f"data: {json.dumps({'text': b.text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
