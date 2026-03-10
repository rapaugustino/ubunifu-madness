"""Tests for conference alias resolution in chat.py."""

import pytest

from app.routers.chat import _CONF_ALIAS_MAP


class TestConfAliasMap:
    """Verify common user abbreviations resolve to correct DB keys."""

    @pytest.mark.parametrize("alias,expected", [
        ("B10", "big_ten"),
        ("BIG10", "big_ten"),
        ("BIG 10", "big_ten"),
        ("BIG TEN", "big_ten"),
        ("B12", "big_twelve"),
        ("BIG12", "big_twelve"),
        ("BIG 12", "big_twelve"),
        ("BIG TWELVE", "big_twelve"),
        ("BE", "big_east"),
        ("BIG EAST", "big_east"),
        ("PAC12", "pac_twelve"),
        ("PAC-12", "pac_twelve"),
        ("PAC 12", "pac_twelve"),
        ("A10", "a_ten"),
        ("A-10", "a_ten"),
        ("ATLANTIC 10", "a_ten"),
        ("ASUN", "a_sun"),
        ("A-SUN", "a_sun"),
        ("ATLANTIC SUN", "a_sun"),
        ("MOUNTAIN WEST", "mwc"),
        ("SUN BELT", "sun_belt"),
        ("SUNBELT", "sun_belt"),
        ("BIG SKY", "big_sky"),
        ("BIG SOUTH", "big_south"),
        ("BIG WEST", "big_west"),
    ])
    def test_alias_resolves(self, alias, expected):
        assert _CONF_ALIAS_MAP[alias] == expected

    def test_all_values_lowercase(self):
        """All resolved DB keys should be lowercase."""
        for val in _CONF_ALIAS_MAP.values():
            assert val == val.lower()

    def test_all_keys_uppercase(self):
        """All alias keys should be uppercase (matching .upper() call in router)."""
        for key in _CONF_ALIAS_MAP:
            assert key == key.upper()

    def test_unknown_alias_not_in_map(self):
        """Unrecognized input should not be in the map (falls through to lowercase)."""
        assert "SEC" not in _CONF_ALIAS_MAP
        assert "ACC" not in _CONF_ALIAS_MAP
        # These are already lowercase DB keys, no alias needed

    def test_resolution_pattern(self):
        """The router uses: _CONF_ALIAS_MAP.get(input.upper(), input.lower())"""
        # Known alias
        user_input = "b10"
        resolved = _CONF_ALIAS_MAP.get(user_input.upper(), user_input.lower())
        assert resolved == "big_ten"

        # Direct DB key (e.g. SEC)
        user_input = "sec"
        resolved = _CONF_ALIAS_MAP.get(user_input.upper(), user_input.lower())
        assert resolved == "sec"

        # Mixed case direct key
        user_input = "ACC"
        resolved = _CONF_ALIAS_MAP.get(user_input.upper(), user_input.lower())
        assert resolved == "acc"
