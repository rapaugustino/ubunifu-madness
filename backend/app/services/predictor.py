"""Prediction service — computes win probabilities from DB state.

Blended prediction approach:
1. If ML model artifacts are in DB → use those (highest quality)
2. Otherwise, blend multiple live signals:
   - Static notebook predictions (trained model output)
   - Current Elo ratings (updated daily from game results)
   - Efficiency metrics (offensive/defensive efficiency diffs)
   - Momentum (recent win% and margin of victory)
   - Conference strength differential

This ensures predictions reflect CURRENT team form, not just a
frozen snapshot from when the notebook was last run.
"""

import io
import logging

import joblib
import numpy as np
from sqlalchemy.orm import Session

from app.models import (
    ModelArtifact, Prediction, EloRating, TeamSeasonStats,
    TourneySeed, TeamConference, ConferenceStrength, Team,
)

logger = logging.getLogger(__name__)

SEASON = 2026

# ---------------------------------------------------------------------------
# Blend weights for combining signals (tuned from backtesting)
# ---------------------------------------------------------------------------

# When static model prediction is available
BLEND_WEIGHTS = {
    "static_model": 0.30,   # Notebook-trained model prediction
    "elo": 0.30,            # Current Elo probability (updated daily)
    "efficiency": 0.05,     # Offensive/defensive efficiency gap
    "momentum": 0.15,       # Recent form (last N games)
    "conference": 0.10,     # Conference strength differential
    "record": 0.10,         # Season win percentage
}

# When only live signals are available (no static prediction)
LIVE_ONLY_WEIGHTS = {
    "elo": 0.35,
    "efficiency": 0.15,
    "momentum": 0.20,
    "conference": 0.15,
    "record": 0.15,
}


# ---------------------------------------------------------------------------
# Model artifact loading (cached)
# ---------------------------------------------------------------------------

class ModelBundle:
    """Holds loaded ML artifacts: LR, LGB, calibrator, metadata."""

    def __init__(self, lr, lgb, calibrator, feature_cols, weights):
        self.lr = lr
        self.lgb = lgb
        self.calibrator = calibrator
        self.feature_cols = feature_cols
        self.weights = weights  # {"lr": float, "lgb": float}


_model_bundle: ModelBundle | None = None
_model_loaded = False


def _load_blob(blob: bytes):
    """Deserialize a joblib blob."""
    return joblib.load(io.BytesIO(blob))


def load_model_bundle(db: Session) -> ModelBundle | None:
    """Load active model artifacts from DB. Returns None if not available."""
    global _model_bundle, _model_loaded

    if _model_loaded:
        return _model_bundle

    artifacts = (
        db.query(ModelArtifact)
        .filter(ModelArtifact.is_active == True)  # noqa: E712
        .all()
    )

    if not artifacts:
        _model_loaded = True
        _model_bundle = None
        return None

    lr = lgb = calibrator = None
    metadata = {}

    for a in artifacts:
        if a.name == "lr_final" and a.artifact_blob:
            lr = _load_blob(a.artifact_blob)
        elif a.name == "lgb_final" and a.artifact_blob:
            lgb = _load_blob(a.artifact_blob)
        elif a.name == "calibrator" and a.artifact_blob:
            calibrator = _load_blob(a.artifact_blob)
        if a.metadata_json:
            metadata.update(a.metadata_json)

    if lr is None and lgb is None:
        _model_loaded = True
        _model_bundle = None
        return None

    feature_cols = metadata.get("feature_cols", [])
    weights = metadata.get("weights", {"lr": 0.5, "lgb": 0.5})

    _model_bundle = ModelBundle(lr, lgb, calibrator, feature_cols, weights)
    _model_loaded = True
    logger.info(f"Loaded model bundle: {len(feature_cols)} features, weights={weights}")
    return _model_bundle


def reload_model_bundle():
    """Force reload on next call (e.g. after uploading new artifacts)."""
    global _model_loaded
    _model_loaded = False


# ---------------------------------------------------------------------------
# Feature building from current DB state
# ---------------------------------------------------------------------------

def _safe_diff(a, b, default=0.0):
    if a is None or b is None:
        return default
    return float(a) - float(b)


def build_matchup_features(
    db: Session,
    team_a_id: int,
    team_b_id: int,
    feature_cols: list[str],
) -> dict[str, float]:
    """Build feature vector for team_a vs team_b from current DB state.

    Feature names match the notebook's build_matchup_features_row() output.
    """
    # Load all data for both teams
    elo_a = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_a_id).first()
    elo_b = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_b_id).first()
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    seed_a = db.query(TourneySeed).filter(TourneySeed.season == SEASON, TourneySeed.team_id == team_a_id).first()
    seed_b = db.query(TourneySeed).filter(TourneySeed.season == SEASON, TourneySeed.team_id == team_b_id).first()
    conf_a = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team_a_id).first()
    conf_b = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team_b_id).first()

    ea = elo_a.elo if elo_a else 1500.0
    eb = elo_b.elo if elo_b else 1500.0
    sa_seed = seed_a.seed_number if seed_a else 8
    sb_seed = seed_b.seed_number if seed_b else 8

    elo_diff = ea - eb
    elo_prob = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))

    # Conference strength
    cs_a = cs_b = None
    if conf_a:
        # Team already imported at module level
        team_obj = db.query(Team).filter(Team.id == team_a_id).first()
        gender = team_obj.gender if team_obj else "M"
        cs_a = db.query(ConferenceStrength).filter(
            ConferenceStrength.season == SEASON,
            ConferenceStrength.gender == gender,
            ConferenceStrength.conf_abbrev == conf_a.conf_abbrev,
        ).first()
    if conf_b:
        # Team already imported at module level
        team_obj = db.query(Team).filter(Team.id == team_b_id).first()
        gender = team_obj.gender if team_obj else "M"
        cs_b = db.query(ConferenceStrength).filter(
            ConferenceStrength.season == SEASON,
            ConferenceStrength.gender == gender,
            ConferenceStrength.conf_abbrev == conf_b.conf_abbrev,
        ).first()

    # Build the raw feature dict (superset — we'll filter to feature_cols)
    f = {}

    # Elo features
    f["elo_a"] = ea
    f["elo_b"] = eb
    f["elo_diff"] = elo_diff
    f["elo_prob"] = elo_prob

    # Seed features
    f["seed_a"] = sa_seed
    f["seed_b"] = sb_seed
    f["seed_diff"] = sa_seed - sb_seed

    # Conference strength diffs
    f["conf_avg_elo_diff"] = _safe_diff(
        cs_a.avg_elo if cs_a else None,
        cs_b.avg_elo if cs_b else None,
    )
    f["conf_nc_winrate_diff"] = _safe_diff(
        cs_a.nc_winrate if cs_a else None,
        cs_b.nc_winrate if cs_b else None,
    )
    f["conf_tourney_hist_winrate_diff"] = _safe_diff(
        cs_a.tourney_hist_winrate if cs_a else None,
        cs_b.tourney_hist_winrate if cs_b else None,
    )

    # Box score diffs (Four Factors + efficiency)
    if stats_a and stats_b:
        f["efg_diff"] = _safe_diff(stats_a.avg_efg_pct, stats_b.avg_efg_pct)
        f["to_diff"] = _safe_diff(stats_a.avg_to_pct, stats_b.avg_to_pct)
        f["or_diff"] = _safe_diff(stats_a.avg_or_pct, stats_b.avg_or_pct)
        f["ftr_diff"] = _safe_diff(stats_a.avg_ft_rate, stats_b.avg_ft_rate)
        f["opp_efg_diff"] = _safe_diff(stats_a.avg_opp_efg_pct, stats_b.avg_opp_efg_pct)
        f["opp_to_diff"] = _safe_diff(stats_a.avg_opp_to_pct, stats_b.avg_opp_to_pct)
        f["off_eff_diff"] = _safe_diff(stats_a.avg_off_eff, stats_b.avg_off_eff)
        f["def_eff_diff"] = _safe_diff(stats_a.avg_def_eff, stats_b.avg_def_eff)
        f["tempo_diff"] = _safe_diff(stats_a.avg_tempo, stats_b.avg_tempo)
        f["win_pct_diff"] = _safe_diff(stats_a.win_pct, stats_b.win_pct)
    else:
        for key in ["efg_diff", "to_diff", "or_diff", "ftr_diff", "opp_efg_diff",
                     "opp_to_diff", "off_eff_diff", "def_eff_diff", "tempo_diff", "win_pct_diff"]:
            f[key] = 0.0

    # Massey ordinals
    f["massey_rank_diff"] = _safe_diff(
        stats_a.massey_avg_rank if stats_a else None,
        stats_b.massey_avg_rank if stats_b else None,
    )
    f["massey_disagreement_diff"] = _safe_diff(
        stats_a.massey_disagreement if stats_a else None,
        stats_b.massey_disagreement if stats_b else None,
    )

    # Momentum
    f["last_n_winpct_diff"] = _safe_diff(
        stats_a.last_n_winpct if stats_a else None,
        stats_b.last_n_winpct if stats_b else None,
    )
    f["last_n_mov_diff"] = _safe_diff(
        stats_a.last_n_mov if stats_a else None,
        stats_b.last_n_mov if stats_b else None,
    )
    f["efg_trend_diff"] = _safe_diff(
        stats_a.efg_trend if stats_a else None,
        stats_b.efg_trend if stats_b else None,
    )

    # Coach
    f["coach_tenure_diff"] = _safe_diff(
        stats_a.coach_tenure if stats_a else None,
        stats_b.coach_tenure if stats_b else None,
    )

    # Conf tourney wins
    f["conf_tourney_wins_diff"] = _safe_diff(
        stats_a.conf_tourney_wins if stats_a else None,
        stats_b.conf_tourney_wins if stats_b else None,
    )

    # SOS
    f["sos_diff"] = _safe_diff(
        stats_a.sos if stats_a else None,
        stats_b.sos if stats_b else None,
    )

    return f


# ---------------------------------------------------------------------------
# Live signal computation
# ---------------------------------------------------------------------------

def _elo_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) from current Elo ratings."""
    elo_a = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_a_id).first()
    elo_b = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_b_id).first()
    if not elo_a or not elo_b:
        return None
    return 1.0 / (1.0 + 10.0 ** ((elo_b.elo - elo_a.elo) / 400.0))


def _efficiency_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) derived from net efficiency differential.

    Net efficiency = offensive_eff - defensive_eff (higher is better).
    Convert the gap to a probability via logistic function.
    """
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.avg_off_eff is None or stats_b.avg_off_eff is None:
        return None

    net_a = (stats_a.avg_off_eff or 0) - (stats_a.avg_def_eff or 0)
    net_b = (stats_b.avg_off_eff or 0) - (stats_b.avg_def_eff or 0)
    diff = net_a - net_b
    # Scale: ~10 point net efficiency gap ≈ 400 Elo points
    return 1.0 / (1.0 + 10.0 ** (-diff / 10.0))


def _momentum_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) based on recent momentum (last N win% and margin)."""
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.last_n_winpct is None or stats_b.last_n_winpct is None:
        return None

    # Combine recent win% and margin of victory
    wp_diff = (stats_a.last_n_winpct or 0.5) - (stats_b.last_n_winpct or 0.5)
    mov_diff = (stats_a.last_n_mov or 0) - (stats_b.last_n_mov or 0)
    # Normalize: win% diff (-1 to 1) and MOV diff (scale by 20)
    combined = wp_diff * 0.6 + (mov_diff / 20.0) * 0.4
    return 1.0 / (1.0 + 10.0 ** (-combined * 3.0))


def _static_model_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) from static Prediction table (notebook output)."""
    lo, hi = min(team_a_id, team_b_id), max(team_a_id, team_b_id)
    pred = (
        db.query(Prediction)
        .filter(Prediction.season == SEASON, Prediction.team_a_id == lo, Prediction.team_b_id == hi)
        .first()
    )
    if not pred:
        return None
    prob = pred.win_prob_a if team_a_id == lo else (1 - pred.win_prob_a)
    return float(prob)


def _conference_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) based on conference strength differential.

    Uses avg Elo of each team's conference and non-conference win rates
    to estimate relative strength of schedule.
    """
    conf_a = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team_a_id).first()
    conf_b = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team_b_id).first()
    if not conf_a or not conf_b:
        return None

    # Get gender from one of the teams
    team = db.query(Team).filter(Team.id == team_a_id).first()
    gender = team.gender if team else "M"

    cs_a = db.query(ConferenceStrength).filter(
        ConferenceStrength.season == SEASON,
        ConferenceStrength.gender == gender,
        ConferenceStrength.conf_abbrev == conf_a.conf_abbrev,
    ).first()
    cs_b = db.query(ConferenceStrength).filter(
        ConferenceStrength.season == SEASON,
        ConferenceStrength.gender == gender,
        ConferenceStrength.conf_abbrev == conf_b.conf_abbrev,
    ).first()
    if not cs_a or not cs_b:
        return None

    # Combine conference avg Elo diff and non-conference win rate diff
    elo_diff = (cs_a.avg_elo or 1500) - (cs_b.avg_elo or 1500)
    nc_wr_diff = (cs_a.nc_winrate or 0.5) - (cs_b.nc_winrate or 0.5)

    # Conference Elo diff as probability (same scale as team Elo)
    conf_elo_prob = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
    # NC win rate diff as probability (shift from 0.5)
    nc_prob = 0.5 + nc_wr_diff * 0.5

    # Weighted average: conference Elo matters more than NC record
    return conf_elo_prob * 0.7 + nc_prob * 0.3


def _record_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) based on season win percentage, adjusted for SOS.

    A team with a .700 record against a tough schedule (SOS 1700) is
    stronger than one with .700 against a weak schedule (SOS 1300).
    """
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.win_pct is None or stats_b.win_pct is None:
        return None

    # SOS-adjusted win percentage:
    # Raw win% + bonus/penalty based on how much harder/easier their schedule is vs average
    avg_sos = 1500.0
    sos_a = stats_a.sos or avg_sos
    sos_b = stats_b.sos or avg_sos
    # Each 100 Elo of SOS above average adds ~0.05 to effective win%
    adj_a = stats_a.win_pct + (sos_a - avg_sos) / 2000.0
    adj_b = stats_b.win_pct + (sos_b - avg_sos) / 2000.0

    wp_diff = adj_a - adj_b
    # Convert to probability: ±0.5 adjusted win_pct gap → ~85% probability
    return 1.0 / (1.0 + 10.0 ** (-wp_diff * 3.0))


# ---------------------------------------------------------------------------
# Prediction (main entry point)
# ---------------------------------------------------------------------------

CONF_TOURNEY_COMPRESSION = 0.80  # Shrink confidence 20% for conference tourney games
TOSSUP_THRESHOLD = 0.55  # Games below this confidence are tossups


def predict_matchup(
    db: Session,
    team_a_id: int,
    team_b_id: int,
    is_conf_tourney: bool = False,
) -> tuple[float, str]:
    """Predict P(team_a wins) by blending multiple signals.

    Args:
        is_conf_tourney: If True, compress probability toward 0.5 to account
            for conference tournament parity (same-conference familiarity).

    Returns (probability, source_label).
    """
    # Layer 1: Try ML model artifacts (best quality when available)
    bundle = load_model_bundle(db)
    if bundle and bundle.feature_cols:
        try:
            features = build_matchup_features(db, team_a_id, team_b_id, bundle.feature_cols)
            X = np.array([[features.get(c, 0.0) for c in bundle.feature_cols]])

            probs = []
            weights = []
            if bundle.lr:
                p = bundle.lr.predict_proba(X)[0][1]
                probs.append(p)
                weights.append(bundle.weights.get("lr", 0.5))
            if bundle.lgb:
                p = bundle.lgb.predict_proba(X)[0][1]
                probs.append(p)
                weights.append(bundle.weights.get("lgb", 0.5))

            if probs:
                total_w = sum(weights)
                raw = sum(p * w for p, w in zip(probs, weights)) / total_w

                if bundle.calibrator:
                    raw = bundle.calibrator.predict(np.array([[raw]]))[0]

                prob = float(np.clip(raw, 0.02, 0.98))
                if is_conf_tourney:
                    prob = 0.5 + (prob - 0.5) * CONF_TOURNEY_COMPRESSION
                return prob, "ml_ensemble"
        except Exception as e:
            logger.warning(f"ML prediction failed, falling back: {e}")

    # Layer 2: Blend available live signals
    signals = {}

    static_prob = _static_model_probability(db, team_a_id, team_b_id)
    if static_prob is not None:
        signals["static_model"] = static_prob

    elo_prob = _elo_probability(db, team_a_id, team_b_id)
    if elo_prob is not None:
        signals["elo"] = elo_prob

    eff_prob = _efficiency_probability(db, team_a_id, team_b_id)
    if eff_prob is not None:
        signals["efficiency"] = eff_prob

    mom_prob = _momentum_probability(db, team_a_id, team_b_id)
    if mom_prob is not None:
        signals["momentum"] = mom_prob

    conf_prob = _conference_probability(db, team_a_id, team_b_id)
    if conf_prob is not None:
        signals["conference"] = conf_prob

    rec_prob = _record_probability(db, team_a_id, team_b_id)
    if rec_prob is not None:
        signals["record"] = rec_prob

    if not signals:
        # Absolute fallback: 50/50
        return 0.5, "no_data"

    # Choose weight scheme based on whether static model is available
    if "static_model" in signals:
        weight_scheme = BLEND_WEIGHTS
        source = "blended"
    else:
        weight_scheme = LIVE_ONLY_WEIGHTS
        source = "live_blend"

    # Weighted average of available signals
    weighted_sum = 0.0
    total_weight = 0.0
    for key, prob in signals.items():
        w = weight_scheme.get(key, 0.0)
        if w > 0:
            weighted_sum += prob * w
            total_weight += w

    if total_weight > 0:
        prob = weighted_sum / total_weight
    else:
        # Fallback: equal-weight average of all signals
        prob = sum(signals.values()) / len(signals)

    # Conference tournament games: compress toward 0.5 (parity adjustment)
    if is_conf_tourney:
        prob = 0.5 + (prob - 0.5) * CONF_TOURNEY_COMPRESSION

    prob = max(0.02, min(0.98, prob))
    return prob, source
