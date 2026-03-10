"""Shared fixtures for backend tests."""

import pytest


@pytest.fixture
def mock_elo_map():
    """Sample Elo ratings for testing."""
    return {
        1001: 2050.0,  # Strong team
        1002: 1800.0,  # Good team
        1003: 1500.0,  # Average team
        1004: 1200.0,  # Weak team
    }
