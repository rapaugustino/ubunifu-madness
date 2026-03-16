"""Admin endpoints for triggering maintenance tasks."""

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_EMAIL = "rapaugustino@gmail.com"


class AuthRequest(BaseModel):
    email: str


class AdminRequest(BaseModel):
    email: str


def _require_admin(body: AdminRequest):
    if body.email != ADMIN_EMAIL:
        raise HTTPException(403, "Unauthorized")


@router.post("/auth")
def auth_check(body: AuthRequest):
    return {"authorized": body.email == ADMIN_EMAIL}


@router.post("/bracket/generate")
def admin_generate_bracket(
    body: AdminRequest,
    gender: str = Query("M", pattern="^(M|W)$"),
    bracket_type: str = Query("model", pattern="^(model|agent)$"),
    season: int = Query(0),
    db: Session = Depends(get_db),
):
    _require_admin(body)
    from app.routers.bracket import generate_official_bracket

    return generate_official_bracket(gender=gender, bracket_type=bracket_type, season=season, db=db)


@router.post("/bracket/reset")
def admin_reset_bracket(
    body: AdminRequest,
    gender: str = Query("M", pattern="^(M|W)$"),
    bracket_type: str = Query("model", pattern="^(model|agent|consensus)$"),
    season: int = Query(0),
    db: Session = Depends(get_db),
):
    """Delete a locked bracket so it can be regenerated. Admin only."""
    _require_admin(body)
    from app.models.official_bracket import OfficialBracket

    actual_season = season if season > 0 else 2026
    existing = (
        db.query(OfficialBracket)
        .filter(
            OfficialBracket.season == actual_season,
            OfficialBracket.gender == gender,
            OfficialBracket.bracket_type == bracket_type,
        )
        .first()
    )
    if not existing:
        return {"status": "not_found", "message": f"No {bracket_type} bracket found for {gender} {actual_season}"}

    db.delete(existing)
    db.commit()
    return {"status": "ok", "message": f"{bracket_type.title()} bracket for {gender} {actual_season} has been reset."}


@router.post("/bracket/consensus")
def admin_generate_consensus(
    body: AdminRequest,
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = Query(0),
    db: Session = Depends(get_db),
):
    _require_admin(body)
    from app.routers.bracket import generate_consensus_bracket

    return generate_consensus_bracket(gender=gender, season=season, db=db)


@router.post("/seeds/refresh")
def admin_refresh_seeds(
    body: AdminRequest,
    gender: str = Query("M", pattern="^(M|W)$"),
    db: Session = Depends(get_db),
):
    _require_admin(body)
    from app.routers.espn import refresh_seeds

    return refresh_seeds(gender=gender, db=db)


@router.post("/cron/run")
def admin_run_cron(body: AdminRequest):
    _require_admin(body)
    try:
        backend_dir = str(Path(__file__).resolve().parent.parent.parent)
        result = subprocess.run(
            [sys.executable, "-m", "scripts.cron_elo_update"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "message": "Cron pipeline timed out after 10 minutes"}
    except Exception as e:
        raise HTTPException(500, f"Failed to run cron: {e}")
