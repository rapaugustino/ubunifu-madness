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
    GameResult,
)

logger = logging.getLogger(__name__)

SEASON = 2026

# ---------------------------------------------------------------------------
# Blend weights for combining signals (tuned from backtesting on 255 conf tourney games)
#
# Backtest results (2026 conference tournament):
#   Elo only:               70.6% acc, 0.1927 Brier
#   Elo 60% + Record 40%:   72.5% acc, 0.1844 Brier  <-- best 2-signal
#   Previous 7-signal:      68.2% acc, 0.1990 Brier   <-- was WORSE than Elo alone
#
# Key finding: ML model, momentum, conf strength add noise during March.
# Elo + Record is the optimal live blend. ML ensemble kept for pre-tournament.
# ---------------------------------------------------------------------------

# When static model prediction is available
BLEND_WEIGHTS = {
    "static_model": 0.15,          # Notebook-trained model — light weight (65% solo acc)
    "elo": 0.50,                   # Primary signal (71% solo, best calibration)
    "advanced_analytics": 0.05,    # Light AdjEM (opponent-adjusted, includes SOS)
    "efficiency": 0.00,            # Disabled — adds noise
    "momentum": 0.00,              # Disabled — unreliable with missing game data
    "conference": 0.00,            # Disabled — Elo already captures this
    "record": 0.30,                # Strong Elo corrector (74% solo acc)
}

# When only live signals are available (no static prediction)
LIVE_ONLY_WEIGHTS = {
    "elo": 0.60,                   # Primary signal
    "advanced_analytics": 0.00,    # Disabled — Elo+Record is optimal
    "efficiency": 0.00,            # Disabled
    "momentum": 0.00,              # Disabled
    "conference": 0.00,            # Disabled — Elo captures conf strength
    "record": 0.40,                # Best Elo corrector (72.5% acc, 0.1844 Brier)
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
    # V3 uses {"weights": {"lr": ..., "lgb": ...}}, V4 uses "lr_weight"/"lgb_weight"
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
    """Apply isotonic calibration with linear interpolation.

    The raw IsotonicRegression.predict() produces a step function with few
    unique output levels (because it was fitted on ~900 tournament games).
    This causes prediction clustering.  Instead, we linearly interpolate
    between the step midpoints to produce a smooth, continuous output.
    """
    xs = calibrator.X_thresholds_
    ys = calibrator.y_thresholds_

    # Build midpoints of each step (consecutive pairs share the same y)
    mid_x = []
    mid_y = []
    i = 0
    while i < len(xs):
        # Find run of identical y values
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
    if a is None or b is None:
        return default
    return float(a) - float(b)


def _compute_rest_days(db: Session, team_id: int) -> int:
    """Days since team's last game. Returns 7 as default."""
    last_game = (
        db.query(GameResult.day_num)
        .filter(
            GameResult.season == SEASON,
            (GameResult.w_team_id == team_id) | (GameResult.l_team_id == team_id),
        )
        .order_by(GameResult.day_num.desc())
        .first()
    )
    if not last_game:
        return 7

    # Get second-to-last to compute gap
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
    """Season head-to-head: returns (win_pct_diff, total_games).
    win_pct_diff is +1 if A swept, -1 if B swept, 0 if no games or split."""
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
    """Win% against top-50 Elo teams. Returns 0.0 if no quality games."""
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
    """Build feature vector for team_a vs team_b from current DB state.

    Feature names match the notebook's build_matchup_features_row() output.
    Supports both V3 (28 features) and V4 (40 features).
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

    # --- V4 features (game context + new signals) ---

    # Game type flags
    f["is_conf_tourney"] = 1.0 if is_conf_tourney else 0.0
    f["is_ncaa_tourney"] = 1.0 if is_ncaa_tourney else 0.0
    f["is_neutral_site"] = 1.0 if is_neutral else 0.0

    # Rest days (days since each team's last game)
    if "rest_days_diff" in feature_cols:
        rest_a = _compute_rest_days(db, team_a_id)
        rest_b = _compute_rest_days(db, team_b_id)
        f["rest_days_diff"] = float(rest_a - rest_b)
    else:
        f["rest_days_diff"] = 0.0

    # Ranking features from Massey Ordinals
    # massey_avg_rank is our best proxy for consensus rank
    # KenPom and NET aren't stored individually — use massey_avg_rank as fallback
    rank_a = stats_a.massey_avg_rank if stats_a and stats_a.massey_avg_rank else 200.0
    rank_b = stats_b.massey_avg_rank if stats_b and stats_b.massey_avg_rank else 200.0
    f["kenpom_rank_diff"] = rank_a - rank_b
    f["net_rank_diff"] = rank_a - rank_b
    f["consensus_rank_diff"] = rank_a - rank_b

    # Adjusted efficiency margin (from advanced_stats.py — already in DB)
    f["adj_eff_margin_diff"] = _safe_diff(
        stats_a.adj_net_eff if stats_a else None,
        stats_b.adj_net_eff if stats_b else None,
    )

    # Barthag (win probability vs average team)
    f["barthag_diff"] = _safe_diff(
        stats_a.barthag if stats_a else None,
        stats_b.barthag if stats_b else None,
    )

    # Quality win percentage (wins vs top-50 Elo teams)
    if "quality_win_pct_diff" in feature_cols:
        # Get top-50 Elo teams
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

    # Raw win percentages (non-differenced — LGB uses for nonlinearities)
    f["win_pct_a"] = float(stats_a.win_pct) if stats_a and stats_a.win_pct is not None else 0.5
    f["win_pct_b"] = float(stats_b.win_pct) if stats_b and stats_b.win_pct is not None else 0.5

    # V5: Head-to-head season record
    if "h2h_win_pct_diff" in feature_cols:
        h2h = _compute_h2h_record(db, team_a_id, team_b_id)
        f["h2h_win_pct_diff"] = h2h[0]
        f["h2h_games"] = h2h[1]
    else:
        f["h2h_win_pct_diff"] = 0.0
        f["h2h_games"] = 0

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


def _advanced_analytics_probability(db: Session, team_a_id: int, team_b_id: int) -> float | None:
    """P(team_a wins) from opponent-adjusted efficiency margin (AdjEM) with luck regression.

    AdjEM is the strongest single predictor of team quality — it measures
    points per 100 possessions above/below average, adjusted for opponent
    strength. Luck (actual W% - Pythagorean W%) is regressed toward zero
    to penalize teams whose record exceeds their underlying quality.
    """
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()
    if not stats_a or not stats_b:
        return None
    if stats_a.adj_net_eff is None or stats_b.adj_net_eff is None:
        return None

    adj_em_diff = stats_a.adj_net_eff - stats_b.adj_net_eff

    # Luck regression: positive luck means overperforming (likely to regress)
    # Each 0.05 luck penalizes ~0.5 AdjEM points
    luck_a = stats_a.luck or 0.0
    luck_b = stats_b.luck or 0.0
    luck_adjustment = (luck_a - luck_b) * -10.0

    effective_diff = adj_em_diff + luck_adjustment

    # Convert to probability: ~10pt AdjEM gap → ~75% win probability
    return 1.0 / (1.0 + 10.0 ** (-effective_diff / 12.0))


# ---------------------------------------------------------------------------
# Prediction (main entry point)
# ---------------------------------------------------------------------------

CONF_TOURNEY_COMPRESSION = 0.95  # Light 5% compression (backtest: no compression is optimal for Elo+Record)
TOSSUP_THRESHOLD = 0.55  # Games below this confidence are tossups


def predict_matchup(
    db: Session,
    team_a_id: int,
    team_b_id: int,
    is_conf_tourney: bool = False,
    is_ncaa_tourney: bool = False,
    is_neutral: bool = True,
) -> tuple[float, str]:
    """Predict P(team_a wins) by blending multiple signals.

    Args:
        is_conf_tourney: Conference tournament game flag.
        is_ncaa_tourney: NCAA tournament game flag.
        is_neutral: Neutral site flag (default True for tournament games).

    Returns (probability, source_label).
    """
    # Layer 1: Try ML model artifacts (best quality when available)
    bundle = load_model_bundle(db)
    if bundle and bundle.feature_cols:
        try:
            features = build_matchup_features(
                db, team_a_id, team_b_id, bundle.feature_cols,
                is_conf_tourney=is_conf_tourney,
                is_ncaa_tourney=is_ncaa_tourney,
                is_neutral=is_neutral,
            )
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
                    raw = _smooth_calibrate(bundle.calibrator, raw)

                prob = float(np.clip(raw, 0.02, 0.98))

                # Conference tournament compression: empirical calibration shows
                # the 70-75% band hits only ~61% in conf tourneys. Shrink toward
                # 50% to reduce overconfidence in volatile postseason games.
                if is_conf_tourney:
                    prob = 0.5 + (prob - 0.5) * 0.85

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

    adv_prob = _advanced_analytics_probability(db, team_a_id, team_b_id)
    if adv_prob is not None:
        signals["advanced_analytics"] = adv_prob

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

    prob = float(np.clip(prob, 0.02, 0.98))
    return prob, source


# ---------------------------------------------------------------------------
# Explanation generator — derives factors from actual feature diffs
# ---------------------------------------------------------------------------

# Feature-to-explanation mapping: (feature_key, label_fn, min_threshold)
# label_fn receives (diff, stats_a, stats_b, favored_is_a) and returns a string or None
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
    """Generate a 1-line explanation from actual model feature diffs.

    Looks at the real feature differences between the teams and reports
    the top 2-3 factors where the favored team has a clear advantage.

    Args:
        prob_a: Pre-computed P(team_a wins). If None, calls predict_matchup.
        is_conf_tourney: Passed to predict_matchup if prob_a is None.
    """
    team_a = db.query(Team).filter(Team.id == team_a_id).first()
    team_b = db.query(Team).filter(Team.id == team_b_id).first()
    if not team_a or not team_b:
        return ""

    # Use the provided probability to stay consistent with the locked prediction
    if prob_a is None:
        prob_a, _ = predict_matchup(
            db, team_a_id, team_b_id, is_conf_tourney=is_conf_tourney
        )
    favored_is_a = prob_a >= 0.5
    favored = team_a if favored_is_a else team_b

    # Load supporting data
    stats_a = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_a_id).first()
    stats_b = db.query(TeamSeasonStats).filter(TeamSeasonStats.season == SEASON, TeamSeasonStats.team_id == team_b_id).first()

    # Build the actual feature diffs (same as what the model sees)
    bundle = load_model_bundle(db)
    feature_cols = bundle.feature_cols if bundle and bundle.feature_cols else []
    if feature_cols:
        features = build_matchup_features(db, team_a_id, team_b_id, feature_cols)
    else:
        features = {}

    # Also compute key diffs directly for robustness
    elo_a = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_a_id).first()
    elo_b = db.query(EloRating).filter(EloRating.season == SEASON, EloRating.team_id == team_b_id).first()
    if "elo_diff" not in features and elo_a and elo_b:
        features["elo_diff"] = elo_a.elo - elo_b.elo
    if "adj_eff_margin_diff" not in features and stats_a and stats_b:
        features["adj_eff_margin_diff"] = _safe_diff(
            stats_a.adj_net_eff, stats_b.adj_net_eff)
    if "win_pct_diff" not in features and stats_a and stats_b:
        features["win_pct_diff"] = _safe_diff(stats_a.win_pct, stats_b.win_pct)

    # Score each explainer: only include factors where the favored team has the advantage
    candidates = []
    for feat_key, label_fn, in _FEATURE_EXPLAINERS:
        diff = features.get(feat_key, 0.0)
        if diff == 0.0:
            continue
        # Check if the diff direction matches the favored team
        favored_has_edge = (favored_is_a and diff > 0) or (not favored_is_a and diff < 0)
        if not favored_has_edge:
            continue
        label = label_fn(diff, stats_a, stats_b, favored_is_a)
        if label:
            candidates.append((abs(diff), label))

    if not candidates:
        return f"{favored.name} favored: ML model edge"

    # Sort by magnitude descending, take top 3
    candidates.sort(key=lambda x: x[0], reverse=True)
    factors = [label for _, label in candidates[:3]]
    return f"{favored.name} favored: {', '.join(factors)}"
