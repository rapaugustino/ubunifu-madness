"""Tests for Elo calculation logic in compute_stats.py."""

import numpy as np
import pandas as pd
import pytest

from scripts.compute_stats import (
    expected_win_prob,
    compute_elo_ratings,
    K_FACTOR,
    HOME_ADV,
    SEASON_REGRESSION,
    MEAN_ELO,
    r,
)


# ---------------------------------------------------------------------------
# expected_win_prob
# ---------------------------------------------------------------------------

class TestExpectedWinProb:
    def test_equal_elo_gives_50_50(self):
        assert expected_win_prob(1500, 1500) == pytest.approx(0.5)

    def test_higher_elo_favored(self):
        prob = expected_win_prob(1800, 1500)
        assert prob > 0.5

    def test_lower_elo_underdog(self):
        prob = expected_win_prob(1200, 1500)
        assert prob < 0.5

    def test_symmetry(self):
        """P(A beats B) + P(B beats A) = 1."""
        p_ab = expected_win_prob(1700, 1400)
        p_ba = expected_win_prob(1400, 1700)
        assert p_ab + p_ba == pytest.approx(1.0)

    def test_400_point_gap(self):
        """A 400-point Elo gap should give ~91% win probability."""
        prob = expected_win_prob(1900, 1500)
        assert prob == pytest.approx(0.909, abs=0.01)

    def test_extreme_gap(self):
        """Very large gap should approach but not exceed 1.0."""
        prob = expected_win_prob(2500, 1000)
        assert 0.99 < prob < 1.0


# ---------------------------------------------------------------------------
# Elo constants
# ---------------------------------------------------------------------------

class TestEloConstants:
    def test_k_factor(self):
        assert K_FACTOR == 21.8

    def test_home_advantage(self):
        assert HOME_ADV == 101.9

    def test_season_regression(self):
        assert SEASON_REGRESSION == 0.89

    def test_mean_elo(self):
        assert MEAN_ELO == 1500


# ---------------------------------------------------------------------------
# Round helper
# ---------------------------------------------------------------------------

class TestRoundHelper:
    def test_normal_value(self):
        assert r(3.14159, 2) == 3.14

    def test_none_returns_none(self):
        assert r(None) is None

    def test_nan_returns_none(self):
        assert r(float("nan")) is None

    def test_returns_python_float(self):
        result = r(np.float64(1.23456), 3)
        assert isinstance(result, float)
        assert result == 1.235


# ---------------------------------------------------------------------------
# compute_elo_ratings (integration with DataFrame)
# ---------------------------------------------------------------------------

class TestComputeEloRatings:
    def _make_game(self, season, day, w_id, w_score, l_id, l_score, w_loc="N"):
        return {
            "Season": season,
            "DayNum": day,
            "WTeamID": w_id,
            "WScore": w_score,
            "LTeamID": l_id,
            "LScore": l_score,
            "WLoc": w_loc,
            "GameType": "regular",
            "Gender": "M",
        }

    def test_single_game_winner_gains_elo(self):
        df = pd.DataFrame([self._make_game(2025, 1, 101, 80, 102, 70)])
        result = compute_elo_ratings(df)
        assert result[(2025, 101)] > MEAN_ELO
        assert result[(2025, 102)] < MEAN_ELO

    def test_single_game_zero_sum(self):
        """Winner's gain equals loser's loss (zero-sum before regression)."""
        df = pd.DataFrame([self._make_game(2025, 1, 101, 80, 102, 70)])
        result = compute_elo_ratings(df)
        gain = result[(2025, 101)] - MEAN_ELO
        loss = MEAN_ELO - result[(2025, 102)]
        assert gain == pytest.approx(loss, abs=0.01)

    def test_home_advantage_applied(self):
        """Home team should gain less Elo for winning (they were favored)."""
        df_home = pd.DataFrame([self._make_game(2025, 1, 101, 80, 102, 70, "H")])
        df_away = pd.DataFrame([self._make_game(2025, 1, 101, 80, 102, 70, "A")])
        df_neut = pd.DataFrame([self._make_game(2025, 1, 101, 80, 102, 70, "N")])

        elo_home = compute_elo_ratings(df_home)[(2025, 101)]
        elo_away = compute_elo_ratings(df_away)[(2025, 101)]
        elo_neut = compute_elo_ratings(df_neut)[(2025, 101)]

        # Winning at home (favored) -> least Elo gain
        # Winning away (underdog) -> most Elo gain
        assert elo_away > elo_neut > elo_home

    def test_season_regression(self):
        """Elo regresses toward mean between seasons."""
        games = [
            self._make_game(2024, 1, 101, 100, 102, 50),  # big win
            self._make_game(2025, 1, 103, 70, 104, 60),    # next season game
        ]
        df = pd.DataFrame(games)
        result = compute_elo_ratings(df)

        # Team 101 had a big win in 2024. By 2025, their Elo should regress.
        elo_2024 = result[(2024, 101)]
        elo_2025 = result[(2025, 101)]
        expected_regressed = elo_2024 * SEASON_REGRESSION + MEAN_ELO * (1 - SEASON_REGRESSION)
        assert elo_2025 == pytest.approx(expected_regressed, abs=0.01)

    def test_margin_of_victory_matters(self):
        """Bigger margin of victory -> more Elo gained."""
        df_close = pd.DataFrame([self._make_game(2025, 1, 101, 71, 102, 70)])
        df_blowout = pd.DataFrame([self._make_game(2025, 1, 101, 100, 102, 60)])

        elo_close = compute_elo_ratings(df_close)[(2025, 101)]
        elo_blowout = compute_elo_ratings(df_blowout)[(2025, 101)]

        assert elo_blowout > elo_close

    def test_new_teams_start_at_mean(self):
        """Teams not seen before start at MEAN_ELO."""
        df = pd.DataFrame([self._make_game(2025, 1, 999, 80, 998, 70)])
        result = compute_elo_ratings(df)
        # Both started at 1500, winner goes up, loser goes down
        assert result[(2025, 999)] > MEAN_ELO
        assert result[(2025, 998)] < MEAN_ELO
