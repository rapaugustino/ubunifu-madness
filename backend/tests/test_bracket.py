"""Tests for bracket construction logic in bracket.py."""

import pytest

from app.routers.bracket import (
    ROUND1_MATCHUPS,
    REGION_NAMES,
    REGION_CODES,
    FF_PAIRINGS,
    ROUND_NAMES,
    _get_pred_from_cache,
)


# ---------------------------------------------------------------------------
# Round 1 matchup structure
# ---------------------------------------------------------------------------

class TestRound1Matchups:
    def test_eight_matchups_per_region(self):
        assert len(ROUND1_MATCHUPS) == 8

    def test_all_16_seeds_present(self):
        """Seeds 1-16 should all appear exactly once."""
        all_seeds = set()
        for a, b in ROUND1_MATCHUPS:
            all_seeds.add(a)
            all_seeds.add(b)
        assert all_seeds == set(range(1, 17))

    def test_standard_first_matchup(self):
        """1 seed plays 16 seed in round 1."""
        assert (1, 16) in ROUND1_MATCHUPS

    def test_standard_second_matchup(self):
        """8 seed plays 9 seed in round 1."""
        assert (8, 9) in ROUND1_MATCHUPS

    def test_seed_pairs_sum(self):
        """Each matchup pair sums to 17 (1+16, 2+15, etc.)."""
        for a, b in ROUND1_MATCHUPS:
            assert a + b == 17

    def test_lower_seed_first(self):
        """In each matchup, the lower (better) seed comes first."""
        for a, b in ROUND1_MATCHUPS:
            assert a < b


# ---------------------------------------------------------------------------
# Region configuration
# ---------------------------------------------------------------------------

class TestRegionConfig:
    def test_four_regions(self):
        assert len(REGION_NAMES) == 4

    def test_region_codes(self):
        assert set(REGION_NAMES.keys()) == {"W", "X", "Y", "Z"}

    def test_region_names(self):
        assert set(REGION_NAMES.values()) == {"East", "West", "South", "Midwest"}

    def test_reverse_mapping(self):
        """REGION_CODES is the inverse of REGION_NAMES."""
        for code, name in REGION_NAMES.items():
            assert REGION_CODES[name] == code

    def test_ff_pairings_cover_all_regions(self):
        """Final Four pairings should include all 4 regions."""
        regions_in_ff = set()
        for a, b in FF_PAIRINGS:
            regions_in_ff.add(a)
            regions_in_ff.add(b)
        assert regions_in_ff == {"W", "X", "Y", "Z"}

    def test_ff_pairings_count(self):
        assert len(FF_PAIRINGS) == 2

    def test_round_names(self):
        assert ROUND_NAMES == ["Round of 64", "Round of 32", "Sweet 16", "Elite 8"]


# ---------------------------------------------------------------------------
# Prediction cache lookup
# ---------------------------------------------------------------------------

class TestPredCache:
    def test_cache_hit_same_order(self):
        cache = {(100, 200): 0.65}
        assert _get_pred_from_cache(cache, 100, 200) == 0.65

    def test_cache_hit_reversed_order(self):
        """When queried in reverse order, probability should flip."""
        cache = {(100, 200): 0.65}
        assert _get_pred_from_cache(cache, 200, 100) == pytest.approx(0.35)

    def test_cache_miss_returns_0_5(self):
        cache = {}
        assert _get_pred_from_cache(cache, 100, 200) == 0.5

    def test_50_50_prediction_symmetric(self):
        cache = {(100, 200): 0.5}
        assert _get_pred_from_cache(cache, 100, 200) == 0.5
        assert _get_pred_from_cache(cache, 200, 100) == 0.5

    def test_extreme_favorite(self):
        cache = {(100, 200): 0.95}
        assert _get_pred_from_cache(cache, 100, 200) == 0.95
        assert _get_pred_from_cache(cache, 200, 100) == pytest.approx(0.05)
