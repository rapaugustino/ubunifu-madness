"""Model performance tracking — locked predictions and accuracy analytics."""


from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GamePrediction

router = APIRouter(tags=["performance"])

SEASON = 2026


# ---------------------------------------------------------------------------
# Performance summary
# ---------------------------------------------------------------------------

@router.get("/performance/summary")
def performance_summary(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = SEASON,
    db: Session = Depends(get_db),
):
    """Overall model accuracy summary."""
    base = db.query(GamePrediction).filter(
        GamePrediction.season == season,
        GamePrediction.gender == gender,
        GamePrediction.model_correct.isnot(None),
    )

    total = base.count()
    if total == 0:
        return {"total": 0, "correct": 0, "accuracy": None, "brierScore": None}

    correct = base.filter(GamePrediction.model_correct == True).count()  # noqa: E712

    # Brier score: mean of (predicted - outcome)^2
    resolved = base.all()
    brier_sum = 0.0
    for gp in resolved:
        predicted_away_win = gp.locked_prob_away
        actual_away_win = 1.0 if gp.away_score > gp.home_score else 0.0
        brier_sum += (predicted_away_win - actual_away_win) ** 2
    brier = brier_sum / total

    # By source
    by_source = {}
    sources = db.query(GamePrediction.prediction_source, func.count()).filter(
        GamePrediction.season == season,
        GamePrediction.gender == gender,
        GamePrediction.model_correct.isnot(None),
    ).group_by(GamePrediction.prediction_source).all()
    for src, cnt in sources:
        src_correct = base.filter(GamePrediction.prediction_source == src, GamePrediction.model_correct == True).count()  # noqa: E712
        by_source[src] = {"total": cnt, "correct": src_correct, "accuracy": round(src_correct / cnt, 4) if cnt > 0 else None}

    # Tossup count (confidence < 55% — raised from 52% for more honest uncertainty)
    tossup_threshold = 0.55
    tossups = sum(1 for gp in resolved if max(gp.locked_prob_away, 1 - gp.locked_prob_away) < tossup_threshold)

    # Accuracy excluding tossups
    confident_games = [gp for gp in resolved if max(gp.locked_prob_away, 1 - gp.locked_prob_away) >= tossup_threshold]
    confident_correct = sum(1 for gp in confident_games if gp.model_correct)
    confident_total = len(confident_games)

    # Accuracy by game type (conf_tourney vs tourney vs regular)
    by_game_type = {}
    game_type_groups = {}
    for gp in resolved:
        gt = gp.game_type or "unknown"
        if gt not in game_type_groups:
            game_type_groups[gt] = {"total": 0, "correct": 0}
        game_type_groups[gt]["total"] += 1
        if gp.model_correct:
            game_type_groups[gt]["correct"] += 1
    for gt, counts in game_type_groups.items():
        by_game_type[gt] = {
            "total": counts["total"],
            "correct": counts["correct"],
            "accuracy": round(counts["correct"] / counts["total"], 4) if counts["total"] > 0 else None,
        }

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4),
        "confidentTotal": confident_total,
        "confidentCorrect": confident_correct,
        "confidentAccuracy": round(confident_correct / confident_total, 4) if confident_total > 0 else None,
        "tossups": tossups,
        "tossupThreshold": tossup_threshold,
        "brierScore": round(brier, 4),
        "bySource": by_source,
        "byGameType": by_game_type,
    }


# ---------------------------------------------------------------------------
# Homepage stats (combined M + W + overall)
# ---------------------------------------------------------------------------

@router.get("/performance/homepage-stats")
def homepage_stats(
    season: int = SEASON,
    db: Session = Depends(get_db),
):
    """Lightweight accuracy stats for the homepage hero section."""
    results = {}
    for gender, label in [("M", "men"), ("W", "women")]:
        resolved = db.query(GamePrediction).filter(
            GamePrediction.season == season,
            GamePrediction.gender == gender,
            GamePrediction.model_correct.isnot(None),
        ).all()
        total = len(resolved)
        correct = sum(1 for gp in resolved if gp.model_correct)
        results[label] = {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total > 0 else None,
        }

    # Overall
    all_total = results["men"]["total"] + results["women"]["total"]
    all_correct = results["men"]["correct"] + results["women"]["correct"]
    results["overall"] = {
        "total": all_total,
        "correct": all_correct,
        "accuracy": round(all_correct / all_total, 4) if all_total > 0 else None,
    }
    return results


# ---------------------------------------------------------------------------
# Daily breakdown
# ---------------------------------------------------------------------------

@router.get("/performance/daily")
def performance_daily(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = SEASON,
    db: Session = Depends(get_db),
):
    """Daily accuracy breakdown for charting."""
    rows = (
        db.query(
            GamePrediction.game_date,
            func.count().label("total"),
            func.sum(case((GamePrediction.model_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
        )
        .filter(
            GamePrediction.season == season,
            GamePrediction.gender == gender,
            GamePrediction.model_correct.isnot(None),
        )
        .group_by(GamePrediction.game_date)
        .order_by(GamePrediction.game_date)
        .all()
    )

    daily = []
    cumulative_total = 0
    cumulative_correct = 0
    for date_str, total, correct in rows:
        cumulative_total += total
        cumulative_correct += correct
        daily.append({
            "date": date_str,
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total > 0 else None,
            "cumulativeTotal": cumulative_total,
            "cumulativeCorrect": cumulative_correct,
            "cumulativeAccuracy": round(cumulative_correct / cumulative_total, 4),
        })

    return {"daily": daily, "gender": gender}


# ---------------------------------------------------------------------------
# Calibration data (binned probabilities vs actual outcomes)
# ---------------------------------------------------------------------------

@router.get("/performance/calibration")
def performance_calibration(
    gender: str = Query("M", pattern="^(M|W)$"),
    season: int = SEASON,
    db: Session = Depends(get_db),
):
    """Calibration curve data — binned predicted probabilities vs actual outcomes."""
    resolved = (
        db.query(GamePrediction)
        .filter(
            GamePrediction.season == season,
            GamePrediction.gender == gender,
            GamePrediction.model_correct.isnot(None),
        )
        .all()
    )

    if not resolved:
        return {"bins": [], "gender": gender}

    # Bin into 10 buckets by confidence level (higher team's win prob)
    bins = {i: {"predicted_sum": 0.0, "actual_sum": 0.0, "count": 0} for i in range(10)}

    for gp in resolved:
        # Always use the favorite's probability for calibration
        prob_away = gp.locked_prob_away
        if prob_away >= 0.5:
            predicted_fav = prob_away
            actual_fav_won = 1.0 if gp.away_score > gp.home_score else 0.0
        else:
            predicted_fav = 1.0 - prob_away
            actual_fav_won = 1.0 if gp.home_score > gp.away_score else 0.0

        bucket = min(int(predicted_fav * 10), 9)
        bins[bucket]["predicted_sum"] += predicted_fav
        bins[bucket]["actual_sum"] += actual_fav_won
        bins[bucket]["count"] += 1

    calibration = []
    for i in range(10):
        b = bins[i]
        if b["count"] > 0:
            calibration.append({
                "binCenter": round((i + 0.5) / 10, 2),
                "avgPredicted": round(b["predicted_sum"] / b["count"], 4),
                "avgActual": round(b["actual_sum"] / b["count"], 4),
                "count": b["count"],
            })

    return {"bins": calibration, "gender": gender}


# ---------------------------------------------------------------------------
# Recent games with predictions
# ---------------------------------------------------------------------------

@router.get("/performance/recent")
def performance_recent(
    gender: str = Query("M", pattern="^(M|W)$"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Recent resolved predictions for display."""
    games = (
        db.query(GamePrediction)
        .filter(
            GamePrediction.gender == gender,
            GamePrediction.model_correct.isnot(None),
        )
        .order_by(GamePrediction.game_date.desc(), GamePrediction.id.desc())
        .limit(limit)
        .all()
    )

    return {
        "games": [
            {
                "id": g.id,
                "espnGameId": g.espn_game_id,
                "date": g.game_date,
                "awayName": g.away_name,
                "homeName": g.home_name,
                "awayScore": g.away_score,
                "homeScore": g.home_score,
                "lockedProbAway": round(g.locked_prob_away, 3),
                "source": g.prediction_source,
                "correct": g.model_correct,
            }
            for g in games
        ],
        "gender": gender,
    }
