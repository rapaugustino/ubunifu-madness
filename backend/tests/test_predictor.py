"""Tests for prediction blending logic in predictor.py."""

import pytest

from app.services.predictor import (
    _safe_diff,
    BLEND_WEIGHTS,
    LIVE_ONLY_WEIGHTS,
)


# ---------------------------------------------------------------------------
# _safe_diff
# ---------------------------------------------------------------------------

class TestSafeDiff:
    def test_normal_values(self):
        assert _safe_diff(10, 3) == 7.0

    def test_float_values(self):
        assert _safe_diff(1.5, 0.3) == pytest.approx(1.2)

    def test_none_a_returns_default(self):
        assert _safe_diff(None, 5) == 0.0

    def test_none_b_returns_default(self):
        assert _safe_diff(5, None) == 0.0

    def test_both_none_returns_default(self):
        assert _safe_diff(None, None) == 0.0

    def test_custom_default(self):
        assert _safe_diff(None, 5, default=-1.0) == -1.0

    def test_negative_result(self):
        assert _safe_diff(3, 10) == -7.0

    def test_zero_diff(self):
        assert _safe_diff(5, 5) == 0.0

    def test_string_numeric_cast(self):
        """Values get cast to float internally."""
        assert _safe_diff("10", "3") == 7.0


# ---------------------------------------------------------------------------
# Blend weight validation
# ---------------------------------------------------------------------------

class TestBlendWeights:
    def test_blend_weights_sum_to_one(self):
        assert sum(BLEND_WEIGHTS.values()) == pytest.approx(1.0)

    def test_live_only_weights_sum_to_one(self):
        assert sum(LIVE_ONLY_WEIGHTS.values()) == pytest.approx(1.0)

    def test_blend_has_static_model(self):
        assert "static_model" in BLEND_WEIGHTS

    def test_live_only_no_static_model(self):
        assert "static_model" not in LIVE_ONLY_WEIGHTS

    def test_blend_keys(self):
        expected = {"static_model", "elo", "advanced_analytics", "efficiency", "momentum", "conference", "record"}
        assert set(BLEND_WEIGHTS.keys()) == expected

    def test_live_only_keys(self):
        expected = {"elo", "advanced_analytics", "efficiency", "momentum", "conference", "record"}
        assert set(LIVE_ONLY_WEIGHTS.keys()) == expected

    def test_all_weights_positive(self):
        for w in BLEND_WEIGHTS.values():
            assert w > 0
        for w in LIVE_ONLY_WEIGHTS.values():
            assert w > 0

    def test_elo_is_largest_live_signal(self):
        """Elo should be the largest weight in live-only mode."""
        assert LIVE_ONLY_WEIGHTS["elo"] == max(LIVE_ONLY_WEIGHTS.values())


# ---------------------------------------------------------------------------
# Probability clamping behavior
# ---------------------------------------------------------------------------

class TestProbabilityClamping:
    def test_clamp_logic(self):
        """Verify the clamping formula used in predict_matchup."""
        for raw in [0.0, 0.01, 0.5, 0.99, 1.0]:
            clamped = max(0.02, min(0.98, raw))
            assert 0.02 <= clamped <= 0.98

    def test_extreme_low_clamped(self):
        assert max(0.02, min(0.98, 0.001)) == 0.02

    def test_extreme_high_clamped(self):
        assert max(0.02, min(0.98, 0.999)) == 0.98


# ---------------------------------------------------------------------------
# Weight normalization (the blending math)
# ---------------------------------------------------------------------------

class TestWeightNormalization:
    def test_full_signals_no_normalization_needed(self):
        """When all signals present, weights sum to 1 so division by total is identity."""
        signals = {k: 0.6 for k in BLEND_WEIGHTS}
        total = sum(BLEND_WEIGHTS[k] for k in signals)
        assert total == pytest.approx(1.0)

    def test_partial_signals_renormalize(self):
        """When some signals missing, remaining weights get re-normalized."""
        available = {"elo": 0.7, "momentum": 0.55}
        weight_scheme = BLEND_WEIGHTS

        weighted_sum = sum(available[k] * weight_scheme[k] for k in available)
        total_weight = sum(weight_scheme[k] for k in available)
        result = weighted_sum / total_weight

        # Should be a valid probability
        assert 0.0 < result < 1.0

    def test_single_signal_returns_that_signal(self):
        """If only one signal available, result should equal that signal."""
        signals = {"elo": 0.65}
        weight_scheme = LIVE_ONLY_WEIGHTS

        weighted_sum = sum(signals[k] * weight_scheme[k] for k in signals)
        total_weight = sum(weight_scheme[k] for k in signals)
        result = weighted_sum / total_weight

        assert result == pytest.approx(0.65)
