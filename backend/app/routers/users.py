"""User accounts (email-only) and bracket persistence."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, UserBracket

router = APIRouter(tags=["users"])

SEASON = 2026
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class IdentifyRequest(BaseModel):
    email: str


class SaveBracketRequest(BaseModel):
    picks: dict
    is_ai_generated: bool = False


@router.post("/users/identify")
def identify_user(req: IdentifyRequest, db: Session = Depends(get_db)):
    """Upsert user by email. Returns userId for bracket operations."""
    email = req.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email format")

    user = db.query(User).filter(User.email == email).first()
    is_new = user is None

    if is_new:
        user = User(email=email)
        db.add(user)
        db.flush()
    else:
        user.last_seen = func.now()

    db.commit()
    return {"userId": user.id, "email": user.email, "isNew": is_new}


@router.put("/users/{user_id}/brackets/{season}/{gender}")
def save_bracket(
    user_id: int,
    season: int,
    gender: str,
    req: SaveBracketRequest,
    db: Session = Depends(get_db),
):
    """Save or update bracket picks for a user."""
    if gender not in ("M", "W"):
        raise HTTPException(400, "Gender must be M or W")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    bracket = db.query(UserBracket).filter(
        UserBracket.user_id == user_id,
        UserBracket.season == season,
        UserBracket.gender == gender,
    ).first()

    if bracket:
        bracket.picks = req.picks
        bracket.is_ai_generated = req.is_ai_generated
        bracket.updated_at = func.now()
    else:
        bracket = UserBracket(
            user_id=user_id,
            season=season,
            gender=gender,
            picks=req.picks,
            is_ai_generated=req.is_ai_generated,
        )
        db.add(bracket)

    db.commit()
    return {"status": "saved", "bracketId": bracket.id}


@router.get("/users/brackets")
def load_bracket(
    email: str = Query(...),
    season: int = Query(SEASON),
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    """Load saved bracket picks by email."""
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"found": False, "picks": None}

    bracket = db.query(UserBracket).filter(
        UserBracket.user_id == user.id,
        UserBracket.season == season,
        UserBracket.gender == gender,
    ).first()

    if not bracket:
        return {"found": False, "picks": None}

    return {
        "found": True,
        "userId": user.id,
        "picks": bracket.picks,
        "isAiGenerated": bracket.is_ai_generated,
        "updatedAt": bracket.updated_at or bracket.created_at,
    }
