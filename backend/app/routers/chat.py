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
    TourneySeed, ConferenceStrength, Prediction,
)

router = APIRouter(tags=["chat"])

SEASON = 2026
MAX_CONTEXT_TEAMS = 15  # limit context size

# --- Rate limiting ---
# Per-IP: 20 requests per 10 minutes, 60 per hour
RATE_WINDOW_SHORT = 600   # 10 minutes
RATE_LIMIT_SHORT = 20
RATE_WINDOW_LONG = 3600   # 1 hour
RATE_LIMIT_LONG = 60

_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str):
    """Raise 429 if IP exceeds rate limits. Cleans up old entries."""
    now = time.time()
    # Clean old timestamps
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW_LONG]

    timestamps = _rate_store[ip]
    recent_short = sum(1 for t in timestamps if now - t < RATE_WINDOW_SHORT)
    recent_long = len(timestamps)

    if recent_short >= RATE_LIMIT_SHORT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_SHORT} requests per {RATE_WINDOW_SHORT // 60} minutes. Please wait a bit.",
        )
    if recent_long >= RATE_LIMIT_LONG:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_LONG} requests per hour. Please try again later.",
        )

    _rate_store[ip].append(now)


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    gender: str = "M"


def _build_context(db: Session, gender: str) -> str:
    """Build a concise data context string for the AI from DB."""
    # Top 25 teams by Elo
    rows = (
        db.query(Team, EloRating)
        .join(EloRating, EloRating.team_id == Team.id)
        .filter(EloRating.season == SEASON, Team.gender == gender)
        .order_by(EloRating.elo.desc())
        .limit(25)
        .all()
    )
    team_ids = [t.id for t, _ in rows]

    stats_map = {
        r.team_id: r
        for r in db.query(TeamSeasonStats)
        .filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id.in_(team_ids))
        .all()
    }
    conf_map = {
        r.team_id: r.conf_abbrev
        for r in db.query(TeamConference)
        .filter(TeamConference.season == SEASON, TeamConference.team_id.in_(team_ids))
        .all()
    }
    seed_map = {
        r.team_id: r.seed_number
        for r in db.query(TourneySeed)
        .filter(TourneySeed.season == SEASON, TourneySeed.team_id.in_(team_ids))
        .all()
    }

    lines = [f"# Top 25 {gender} Teams ({SEASON})"]
    lines.append("Rank | Team | Elo | Record | Conf | Seed")
    for i, (team, elo_row) in enumerate(rows):
        s = stats_map.get(team.id)
        rec = f"{s.wins}-{s.losses}" if s else "?"
        seed = seed_map.get(team.id, "-")
        conf = conf_map.get(team.id, "?")
        lines.append(f"{i+1}. {team.name} | Elo {elo_row.elo:.0f} | {rec} | {conf} | Seed {seed}")

    # Conference strength
    cs_rows = (
        db.query(ConferenceStrength)
        .filter(ConferenceStrength.season == SEASON, ConferenceStrength.gender == gender)
        .order_by(ConferenceStrength.avg_elo.desc())
        .limit(10)
        .all()
    )
    lines.append(f"\n# Top 10 Conferences by Avg Elo ({gender})")
    for cs in cs_rows:
        lines.append(
            f"- {cs.conf_abbrev}: avg Elo {cs.avg_elo:.0f}, "
            f"depth {cs.elo_depth:.2f}, NC win rate {(cs.nc_winrate or 0)*100:.1f}%"
        )

    return "\n".join(lines)


def _get_matchup_context(db: Session, team_a_name: str, team_b_name: str, gender: str) -> str | None:
    """Try to find prediction for two teams mentioned by name."""
    a = db.query(Team).filter(Team.gender == gender, Team.name.ilike(f"%{team_a_name}%")).first()
    b = db.query(Team).filter(Team.gender == gender, Team.name.ilike(f"%{team_b_name}%")).first()
    if not a or not b:
        return None

    lo, hi = min(a.id, b.id), max(a.id, b.id)
    pred = (
        db.query(Prediction)
        .filter(Prediction.season == SEASON, Prediction.team_a_id == lo, Prediction.team_b_id == hi)
        .first()
    )
    if not pred:
        return None

    prob_a = pred.win_prob_a if a.id == lo else (1 - pred.win_prob_a)
    return (
        f"\nMatchup prediction: {a.name} vs {b.name} — "
        f"{a.name} win probability: {prob_a*100:.1f}%, "
        f"{b.name} win probability: {(1-prob_a)*100:.1f}%"
    )


SYSTEM_PROMPT = """You are the Ubunifu Madness bracket advisor — an AI assistant for NCAA March Madness predictions.

You have access to real model predictions (LightGBM + Logistic Regression ensemble, Brier score 0.1413) including Elo ratings, conference strength, box score stats (Four Factors), and win probabilities for every possible matchup.

Rules:
- Ground all answers in the data provided. Cite specific numbers (Elo, win %, records).
- Be concise and direct. Use bullet points (- ) for comparisons.
- NEVER use markdown formatting: no ** for bold, no ## for headers, no ` backticks. Use plain text only.
- If you don't have data for something, say so honestly.
- No betting advice. This is for bracket strategy only.
- Keep responses short (2-4 paragraphs max).

The data context below shows the current top 25 teams and conference rankings."""


@router.post("/chat")
def chat(req: ChatRequest, request: Request, db: Session = Depends(get_db)):
    # Rate limit by IP
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    _check_rate_limit(client_ip.split(",")[0].strip())

    context = _build_context(db, req.gender)

    system = f"{SYSTEM_PROMPT}\n\n{context}"

    # Convert messages
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate():
        with client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
