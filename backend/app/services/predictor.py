"""
Prediction service for NCAA basketball win probabilities.

Two-layer approach:
  1. ML ensemble (LR + LightGBM with isotonic calibration) when model
     artifacts are available in the database.
  2. Fallback: weighted blend of live signals (Elo, record, efficiency)
     when ML artifacts are missing.

Predictions are further adjusted for conference tournament context
and recalibrated to correct observed overconfidence at high levels.
"""

import io
import logging

import joblib
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models import (
    ModelArtifact, Prediction, EloRating, TeamSeasonStats,
    TourneySeed, TeamConference, ConferenceStrength, Team,
    GameResult,
)

logger = logging.getLogger(__name__)

SEASON = 2026

# ---------------------------------------------------------------------------
# Blend weights (fallback when ML artifacts unavailable)
#
# Tuned on 255 conference tournament games (2026):
#   Elo only:             70.6% accuracy, 0.1927 Brier
#   Elo 60% + Record 40%: 72.5% accuracy, 0.1844 Brier  (best 2-signal)
#   Previous 7-signal:    68.2% accuracy, 0.1990 Brier   (worse than Elo alone)
#
# Conclusion: momentum, conference strength, raw efficiency add noise in
# March. Elo + Record is the optimal fallback blend.
# ---------------------------------------------------------------------------

BLEND_WEIGHTS = {
    "static_model": 0.15,
    "elo": 0.50,
    "advanced_analytics": 0.05,
    "efficiency": 0.00,
    "momentum": 0.00,
    "conference": 0.00,
    "record": 0.30,
}

LIVE_ONLY_WEIGHTS = {
    "elo": 0.60,
    "advanced_analytics": 0.00,
    "efficiency": 0.00,
    "momentum": 0.00,
    "conference": 0.00,
    "record": 0.40,
}


# ---------------------------------------------------------------------------
# Model artifact loading (cached in memory)
# ---------------------------------------------------------------------------

class ModelBundle:
    """Container for loaded ML model artifacts."""

    def __init__(self, lr, lgb, calibrator, feature_cols, weights):
        self.lr = lr
        self.lgb = lgb
        self.calibrator = calibrator
        self.feature_cols = feature_cols
        self.weights = weights  # e.g. {"lr": 0.378, "lgb": 0.622}


_model_bundle: ModelBundle | None = None
_model_loaded = False


def _load_blob(blob: bytes):
    """Deserialize a joblib-serialized blob from the database."""
    return joblib.load(io.BytesIO(blob))


def load_model_bundle(db: Session) -> ModelBundle | None:
    """Load active model artifacts from DB. Caches after first call."""
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
        try:
            if a.name == "lr_final" and a.artifact_blob:
                lr = _load_blob(a.artifact_blob)
            elif a.name == "lgb_final" and a.artifact_blob:
                lgb = _load_blob(a.artifact_blob)
            elif a.name == "calibrator" and a.artifact_blob:
                calibrator = _load_blob(a.artifact_blob)
        except (OSError, Exception) as e:
            logger.warning(f"Failed to load artifact '{a.name}': {e}")
        if a.metadata_json:
            metadata.update(a.metadata_json)

    if lr is None and lgb is None:
        _model_loaded = True
        _model_bundle = None
        return None

    feature_cols = metadata.get("feature_cols", [])
    weights = metadata.get("weights")
    if not weights:
        weights = {
            "lr": metadata.get("lr_weight", 0.5),
            "lgb": metadata.get("lgb_weight", 0.5),
        }

    _model_bundle = ModelBundle(lr, lgb, calibrator, feature_cols, weights)
    _model_loaded = True
    logger.info(f"Loaded model bundle: {len(feature_cols)} features, weights={weights}")
    return _model_bundle


def reload_model_bundle():
    """Force reload on next call (e.g. after uploading new artifacts)."""
    global _model_loaded
    _model_loaded = False


def _smooth_calibrate(calibrator, raw: float) -> float:
    """Apply isotonic calibration with linear interpolation between steps.

    The raw IsotonicRegression.predict() produces a step function with few
    unique output levels (fitted on ~900 tournament games), which causes
    prediction clustering. We interpolate between step midpoints instead
    to get smooth, continuous probabilities.
    """
    xs = calibrator.X_thresholds_
    ys = calibrator.y_thresholds_

    # Build midpoints of each constant-y segment
    mid_x = []
    mid_y = []
    i = 0
    while i < len(xs):
        j = i
        while j < len(xs) - 1 and ys[j + 1] == ys[j]:
            j += 1
        mid_x.append((xs[i] + xs[j]) / 2)
        mid_y.append(ys[i])
        i = j + 1

    if len(mid_x) < 2:
        return float(calibrator.predict(np.array([[raw]]))[0])

    return float(np.clip(np.interp(raw, mid_x, mid_y), 0.02, 0.98))


# ---------------------------------------------------------------------------
# Feature building from current DB state
# ---------------------------------------------------------------------------

def _safe_diff(a, b, default=0.0):
    """Compute a - b, returning default if either value is None."""
    if a is None or b is None:
        return default
    return float(a) - float(b)


def _compute_rest_days(db: Session, team_id: int) -> int:
    """Gap in days between a team's two most recent games. Defaults to 7."""
    games = (
        db.query(GameResult.day_num)
        .filter(
            GameResult.season == SEASON,
            (GameResult.w_team_id == team_id) | (GameResult.l_team_id == team_id),
        )
        .order_by(GameResult.day_num.desc())
        .limit(2)
        .all()
    )
    if len(games) < 2:
        return 7
    return max(games[0][0] - games[1][0], 1)


def _compute_h2h_record(db: Session, team_a_id: int, team_b_id: int) -> tuple[float, int]:
    """Season head-to-head record between two teams.

    Returns (win_pct_diff, total_games) where win_pct_diff ranges from
    +1 (A swept) to -1 (B swept), 0 if no meetings or even split.
    """
    wins_a = db.query(GameResult).filter(
        GameResult.season == SEASON,
        GameResult.w_team_id == team_a_id,
        GameResult.l_team_id == team_b_id,
    ).count()
    wins_b = db.query(GameResult).filter(
        GameResult.season == SEASON,
        GameResult.w_team_id == team_b_id,
        GameResult.l_team_id == team_a_id,
    ).count()
    total = wins_a + wins_b
    if total == 0:
        return 0.0, 0
    return (wins_a - wins_b) / total, total


def _compute_quality_win_pct(db: Session, team_id: int, top_elos: set[int]) -> float:
    """Win percentage against top-50 Elo teams this season."""
    quality_wins = db.query(GameResult).filter(
        GameResult.season == SEASON,
        GameResult.w_team_id == team_id,
        GameResult.l_team_id.in_(top_elos),
    ).count()
    quality_losses = db.query(GameResult).filter(
        GameResult.season == SEASON,
        GameResult.l_team_id == team_id,
        GameResult.w_team_id.in_(top_elos),
    ).count()
    total = quality_wins + quality_losses
    return quality_wins / total if total > 0 else 0.0


def build_matchup_features(
    db: Session,
    team_a_id: int,
    team_b_id: int,
    feature_cols: list[str],
    *,
    is_conf_tourney: bool = False,
    is_ncaa_tourney: bool = False,
    is_neutral: bool = True,
) -> dict[str, float]:
    """Build the feature vector for a team_a vs team_b matchup.

    Computes all features as (team_a - team_b) diffs from current DB state.
    Feature names match the training notebook's output so the loaded models
    can score them directly. Supports both 28-feature (V3) and 40-feature
    (V4/V5) configurations.
    """
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

    # Conference strength lookups
    cs_a = cs_b = None
    if conf_a:
        team_obj = db.query(Team).filter(Team.id == team_a_id).first()
        gender = team_obj.gender if team_obj else "M"
        cs_a = db.query(ConferenceStrength).filter(
            ConferenceStrength.season == SEASON,
            ConferenceStrength.gender == gender,
            ConferenceStrength.conf_abbrev == conf_a.conf_abbrev,
        ).first()
    if conf_b:
        team_obj = db.query(Team).filter(Team.id == team_b_id).first()
        gender = team_obj.gender if team_obj else "M"
        cs_b = db.query(ConferenceStrength).filter(
            ConferenceStrength.season == SEASON,
            ConferenceStrength.gender == gender,
            ConferenceStrength.conf_abbrev == conf_b.conf_abbrev,
        ).first()

    # Build full feature dict (superset; filtered to feature_cols by caller)
    f = {}

    # -- Elo --
    f["elo_a"] = ea
    f["elo_b"] = eb
    f["elo_diff"] = elo_diff
    f["elo_prob"] = elo_prob

    # -- Seeds --
    f["seed_a"] = sa_seed
    f["seed_b"] = sb_seed
    f["seed_diff"] = sa_seed - sb_seed

    # -- Conference strength diffs --
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

    # -- Four Factors + efficiency diffs --
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

    # -- Massey ordinals --
    f["massey_rank_diff"] = _safe_diff(
        stats_a.massey_avg_rank if stats_a else None,
        stats_b.massey_avg_rank if stats_b else None,
    )
    f["massey_disagreement_diff"] = _safe_diff(
        stats_a.massey_disagreement if stats_a else None,
        stats_b.massey_disagreement if stats_b else None,
    )

    # -- Momentum --
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

    # -- Coaching --
    f["coach_tenure_diff"] = _safe_diff(
        stats_a.coach_tenure if stats_a else None,
        stats_b.coach_tenure if stats_b else None,
    )
    f["conf_tourney_wins_diff"] = _safe_diff(
        stats_a.conf_tourney_wins if stats_a else None,
        stats_b.conf_tourney_wins if stats_b else None,
    )

    # -- Strength of schedule --
    f["sos_diff"] = _safe_diff(
        stats_a.sos if stats_a else None,
        stats_b.sos if stats_b else None,
    )

    # -- V4+ features: game context flags --
    f["is_conf_tourney"] = 1.0 if is_conf_tourney else 0.0
    f["is_ncaa_tourney"] = 1.0 if is_ncaa_tourney else 0.0
    f["is_neutral_site"] = 1.0 if is_neutral else 0.0

    # Rest days (computed on demand since it requires extra queries)
    if "rest_days_diff" in feature_cols:
        rest_a = _compute_rest_days(db, team_a_id)
        rest_b = _compute_rest_days(db, team_b_id)
        f["rest_days_diff"] = float(rest_a - rest_b)
    else:
        f["rest_days_diff"] = 0.0

    # Ranking proxies: massey_avg_rank is our best stand-in for
    # KenPom/NET/consensus since we don't store those individually.
    rank_a = stats_a.massey_avg_rank if stats_a and stats_a.massey_avg_rank else 200.0
    rank_b = stats_b.massey_avg_rank if stats_b and stats_b.massey_avg_rank else 200.0
    f["kenpom_rank_diff"] = rank_a - rank_b
    f["net_rank_diff"] = rank_a - rank_b
    f["consensus_rank_diff"] = rank_a - rank_b

    # Adjusted efficiency margin (opponent-adjusted, home-court-corrected)
    f["adj_eff_margin_diff"] = _safe_diff(
        stats_a.adj_net_eff if stats_a else None,
        stats_b.adj_net_eff if stats_b else None,
    )

    # Barthag (Pythagorean win probability vs average team)
    f["barthag_diff"] = _safe_diff(
        stats_a.barthag if stats_a else None,
        stats_b.barthag if stats_b else None,
    )

    # Quality win percentage (record against top-50 Elo opponents)
    if "quality_win_pct_diff" in feature_cols:
        top_elos = {
            r.team_id for r in
            db.query(EloRating.team_id)
            .filter(EloRating.season == SEASON)
            .order_by(EloRating.elo.desc())
            .limit(50)
            .all()
        }
        qw_a = _compute_quality_win_pct(db, team_a_id, top_elos)
        qw_b = _compute_quality_win_pct(db, team_b_id, top_elos)
        f["quality_win_pct_diff"] = qw_a - qw_b
    else:
        f["quality_win_pct_diff"] = 0.0

    # Raw win percentages (non-differenced, for LightGBM nonlinear splits)
    f["win_pct_a"] = float(stats_a.win_pct) if stats_a and stats_a.win_pct is not None else 0.5
    f["win_pct_b"] = float(stats_b.win_pct) if stats_b and stats_b.win_pct is not None else 0.5

    # Head-to-head record (kept for explanations only, removed from training
    # due to label leakage with conference tournament rematches)
    if "h2h_win_pct_diff" in feature_cols:
        h2h = _compute_h2h_record(db, team_a_id, team_b_id)
        f["h2h_win_pct_diff"] = h2h[0]
        f["h2h_games"] = h2h[1]
    else:
        f["h2h_win_pct_diff"] = 0.0
        f["h2h_games"] = 0

    return f


# ---------------------------------------------------------------------------
# Live signal computation (fallback layer)
# ---------------------------------------------------------------------------

def _elo_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """Win probability from current Elo ratings (logistic model)."""
    elo_a = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_a_id).first()
    elo_b = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_b_id).first()
    if not elo_a or not elo_b:
        return None
    return 1.0 / (1.0 + 10.0 ** ((elo_b.elo - elo_a.elo) / 400.0))


def _efficiency_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """Win probability from raw net efficiency differential.

    Net efficiency = offensive_eff - defensive_eff. A 10-point gap maps
    roughly to a 75% win probability via logistic scaling.
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
    return 1.0 / (1.0 + 10.0 ** (-diff / 10.0))


def _momentum_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """Win probability based on recent form (last-10 win% and margin)."""
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.last_n_winpct is None or stats_b.last_n_winpct is None:
        return None

    wp_diff = (stats_a.last_n_winpct or 0.5) - (stats_b.last_n_winpct or 0.5)
    mov_diff = (stats_a.last_n_mov or 0) - (stats_b.last_n_mov or 0)
    combined = wp_diff * 0.6 + (mov_diff / 20.0) * 0.4
    return 1.0 / (1.0 + 10.0 ** (-combined * 3.0))


def _static_model_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """Win probability from the static Prediction table (notebook output)."""
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
    """Win probability from conference strength differential.

    Blends conference average Elo (70%) with non-conference win rate (30%)
    to estimate relative schedule strength.
    """
    conf_a = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team_a_id).first()
    conf_b = db.query(TeamConference).filter(TeamConference.season == SEASON, TeamConference.team_id == team_b_id).first()
    if not conf_a or not conf_b:
        return None

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

    elo_diff = (cs_a.avg_elo or 1500) - (cs_b.avg_elo or 1500)
    nc_wr_diff = (cs_a.nc_winrate or 0.5) - (cs_b.nc_winrate or 0.5)

    conf_elo_prob = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
    nc_prob = 0.5 + nc_wr_diff * 0.5

    return conf_elo_prob * 0.7 + nc_prob * 0.3


def _record_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """Win probability from SOS-adjusted season record.

    Raw win% is adjusted by strength of schedule: each 100 Elo points
    of SOS above average adds ~0.05 to effective win percentage.
    """
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.win_pct is None or stats_b.win_pct is None:
        return None

    avg_sos = 1500.0
    sos_a = stats_a.sos or avg_sos
    sos_b = stats_b.sos or avg_sos
    adj_a = stats_a.win_pct + (sos_a - avg_sos) / 2000.0
    adj_b = stats_b.win_pct + (sos_b - avg_sos) / 2000.0

    wp_diff = adj_a - adj_b
    return 1.0 / (1.0 + 10.0 ** (-wp_diff * 3.0))


def _advanced_analytics_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """Win probability from opponent-adjusted efficiency margin (AdjEM).

    AdjEM measures points per 100 possessions above/below average, adjusted
    for opponent strength. Luck (actual win% minus Pythagorean win%) is
    regressed toward zero to penalize teams overperforming their efficiency.
    """
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.adj_net_eff is None or stats_b.adj_net_eff is None:
        return None

    adj_em_diff = stats_a.adj_net_eff - stats_b.adj_net_eff

    # Luck regression: +0.05 luck penalizes ~0.5 AdjEM points
    luck_a = stats_a.luck or 0.0
    luck_b = stats_b.luck or 0.0
    luck_adjustment = (luck_a - luck_b) * -10.0

    effective_diff = adj_em_diff + luck_adjustment
    return 1.0 / (1.0 + 10.0 ** (-effective_diff / 12.0))


# ---------------------------------------------------------------------------
# Post-prediction adjustments
# ---------------------------------------------------------------------------

CONF_TOURNEY_COMPRESSION = 0.95
TOSSUP_THRESHOLD = 0.55


def _recalibrate_high_confidence(prob: float) -> float:
    """Compress high-confidence predictions toward 50%.

    Live 2026 calibration (333 games) shows systematic overconfidence
    above ~72%:
        80-85% predicted, 67.6% actual  (-14.6% gap)
        85-90% predicted, 78.0% actual  (-9.3% gap)
        90-95% predicted, 83.3% actual  (-8.4% gap)

    Applies a linear 25% compression to the portion of confidence
    exceeding 72%. Below that threshold, predictions pass through
    unchanged. The function is symmetric around 50%.

    Examples:
        72% -> 72.0%   (no change at threshold)
        80% -> 77.6%
        90% -> 84.6%
        95% -> 88.1%
    """
    THRESHOLD = 0.72
    COMPRESSION = 0.25

    confidence = abs(prob - 0.5)
    threshold_dist = THRESHOLD - 0.5

    if confidence <= threshold_dist:
        return prob

    excess = confidence - threshold_dist
    compressed_excess = excess * (1 - COMPRESSION)
    new_confidence = threshold_dist + compressed_excess

    if prob >= 0.5:
        return 0.5 + new_confidence
    else:
        return 0.5 - new_confidence


# ---------------------------------------------------------------------------
# Main prediction entry point
# ---------------------------------------------------------------------------

def predict_matchup(
    db: Session,
    team_a_id: int,
    team_b_id: int,
    is_conf_tourney: bool = False,
    is_ncaa_tourney: bool = False,
    is_neutral: bool = True,
) -> tuple[float, str]:
    """Predict P(team_a wins) and return (probability, source_label).

    Tries the ML ensemble first; falls back to a weighted blend of
    Elo + record if model artifacts are unavailable. Applies conference
    tournament compression and high-confidence recalibration.
    """
    # Layer 1: ML ensemble (preferred)
    bundle = load_model_bundle(db)
    if bundle and bundle.feature_cols:
        try:
            features = build_matchup_features(
                db, team_a_id, team_b_id, bundle.feature_cols,
                is_conf_tourney=is_conf_tourney,
                is_ncaa_tourney=is_ncaa_tourney,
                is_neutral=is_neutral,
            )
            X_values = np.array([[features.get(c, 0.0) for c in bundle.feature_cols]])
            X_df = pd.DataFrame(X_values, columns=bundle.feature_cols)

            probs = []
            weights = []
            if bundle.lr:
                # LR was trained without feature names -- pass raw array
                p = bundle.lr.predict_proba(X_values)[0][1]
                probs.append(p)
                weights.append(bundle.weights.get("lr", 0.5))
            if bundle.lgb:
                # LightGBM was trained with feature names -- pass DataFrame
                p = bundle.lgb.predict_proba(X_df)[0][1]
                probs.append(p)
                weights.append(bundle.weights.get("lgb", 0.5))

            if probs:
                total_w = sum(weights)
                raw = sum(p * w for p, w in zip(probs, weights)) / total_w

                if bundle.calibrator:
                    raw = _smooth_calibrate(bundle.calibrator, raw)

                prob = float(np.clip(raw, 0.02, 0.98))

                # Women's conf tourney games get 10% compression toward 50%.
                # Men's conf tourney games need no compression (calibration is fine).
                # Based on analysis of 270 conf tourney games (153M, 117W).
                if is_conf_tourney:
                    gender = db.query(Team.gender).filter(Team.id == team_a_id).scalar()
                    factor = 0.90 if gender == "W" else 1.0
                    if factor < 1.0:
                        prob = 0.5 + (prob - 0.5) * factor

                prob = _recalibrate_high_confidence(prob)
                return prob, "ml_ensemble"
        except Exception as e:
            logger.warning(f"ML prediction failed, falling back: {e}")

    # Layer 2: weighted blend of live signals
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

    adv_prob = _advanced_analytics_probability(db, team_a_id, team_b_id)
    if adv_prob is not None:
        signals["advanced_analytics"] = adv_prob

    if not signals:
        return 0.5, "no_data"

    # Pick weight scheme based on what signals are available
    if "static_model" in signals:
        weight_scheme = BLEND_WEIGHTS
        source = "blended"
    else:
        weight_scheme = LIVE_ONLY_WEIGHTS
        source = "live_blend"

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
        prob = sum(signals.values()) / len(signals)

    if is_conf_tourney:
        prob = 0.5 + (prob - 0.5) * CONF_TOURNEY_COMPRESSION

    prob = float(np.clip(prob, 0.02, 0.98))
    prob = _recalibrate_high_confidence(prob)
    return prob, source


# ---------------------------------------------------------------------------
# Matchup explanation generator
# ---------------------------------------------------------------------------

# Each tuple: (feature_key, label_fn)
# label_fn(diff, stats_a, stats_b, favored_is_a) returns a string or None.
_FEATURE_EXPLAINERS = [
    ("elo_diff", lambda d, sa, sb, fa: f"{abs(d):+.0f} Elo edge" if abs(d) >= 30 else None),
    ("adj_eff_margin_diff", lambda d, sa, sb, fa: f"{abs(d):+.1f} AdjEM advantage" if abs(d) >= 1.0 else None),
    ("win_pct_diff", lambda d, sa, sb, fa: (
        f"stronger record ({sa.wins}-{sa.losses} vs {sb.wins}-{sb.losses})"
        if fa and sa and sb and sa.wins is not None and sb.wins is not None
        else (f"stronger record ({sb.wins}-{sb.losses} vs {sa.wins}-{sa.losses})"
              if not fa and sa and sb and sb.wins is not None and sa.wins is not None
              else None)
    ) if abs(d) >= 0.05 else None),
    ("last_n_winpct_diff", lambda d, sa, sb, fa: (
        f"hot streak ({round((sa.last_n_winpct or 0.5) * 100)}% last 10)"
        if fa and sa else
        (f"hot streak ({round((sb.last_n_winpct or 0.5) * 100)}% last 10)"
         if not fa and sb else None)
    ) if abs(d) >= 0.15 else None),
    ("sos_diff", lambda d, sa, sb, fa: f"tougher schedule (SOS {abs(d):.0f})" if abs(d) >= 30 else None),
    ("barthag_diff", lambda d, sa, sb, fa: f"higher Barthag ({abs(d):.3f})" if abs(d) >= 0.03 else None),
    ("massey_rank_diff", lambda d, sa, sb, fa: f"better rankings (Massey {abs(d):.0f} spots)" if abs(d) >= 20 else None),
    ("quality_win_pct_diff", lambda d, sa, sb, fa: f"more quality wins" if abs(d) >= 0.1 else None),
    ("h2h_win_pct_diff", lambda d, sa, sb, fa: f"owns head-to-head" if abs(d) >= 0.5 else None),
]


def explain_matchup(
    db: Session,
    team_a_id: int,
    team_b_id: int,
    prob_a: float | None = None,
    is_conf_tourney: bool = False,
) -> str:
    """Generate a one-line explanation of why one team is favored.

    Reports the top 2-3 feature differences where the favored team has
    a clear edge, using the same features the model sees.

    If prob_a is provided, uses that probability (to stay consistent with
    a locked prediction). Otherwise computes a fresh prediction.
    """
    team_a = db.query(Team).filter(Team.id == team_a_id).first()
    team_b = db.query(Team).filter(Team.id == team_b_id).first()
    if not team_a or not team_b:
        return ""

    if prob_a is None:
        prob_a, _ = predict_matchup(
            db, team_a_id, team_b_id, is_conf_tourney=is_conf_tourney
        )
    favored_is_a = prob_a >= 0.5
    favored = team_a if favored_is_a else team_b

    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()

    # Build feature diffs (same values the model scores on)
    bundle = load_model_bundle(db)
    feature_cols = bundle.feature_cols if bundle and bundle.feature_cols else []
    if feature_cols:
        features = build_matchup_features(db, team_a_id, team_b_id, feature_cols)
    else:
        features = {}

    # Fill in key diffs directly if not already present
    elo_a = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_a_id).first()
    elo_b = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_b_id).first()
    if "elo_diff" not in features and elo_a and elo_b:
        features["elo_diff"] = elo_a.elo - elo_b.elo
    if "adj_eff_margin_diff" not in features and stats_a and stats_b:
        features["adj_eff_margin_diff"] = _safe_diff(
            stats_a.adj_net_eff, stats_b.adj_net_eff)
    if "win_pct_diff" not in features and stats_a and stats_b:
        features["win_pct_diff"] = _safe_diff(stats_a.win_pct, stats_b.win_pct)

    # Only include factors where the favored team has the advantage
    candidates = []
    for feat_key, label_fn in _FEATURE_EXPLAINERS:
        diff = features.get(feat_key, 0.0)
        if diff == 0.0:
            continue
        favored_has_edge = (favored_is_a and diff > 0) or (not favored_is_a and diff < 0)
        if not favored_has_edge:
            continue
        label = label_fn(diff, stats_a, stats_b, favored_is_a)
        if label:
            candidates.append((abs(diff), label))

    if not candidates:
        return f"{favored.name} favored: ML model edge"

    candidates.sort(key=lambda x: x[0], reverse=True)
    factors = [label for _, label in candidates[:3]]
    return f"{favored.name} favored: {', '.join(factors)}"
