"""Tests for chat rate limiting logic."""

import time

import pytest
from fastapi import HTTPException

from app.routers.chat import (
    _check_rate_limit,
    _rate_store,
    RATE_LIMIT_SHORT,
    RATE_LIMIT_LONG,
    RATE_LIMIT_DAILY,
    RATE_WINDOW_SHORT,
)


@pytest.fixture(autouse=True)
def clear_rate_store():
    """Clear rate store before each test."""
    _rate_store.clear()
    yield
    _rate_store.clear()


class TestRateLimit:
    def test_first_request_passes(self):
        _check_rate_limit("1.2.3.4")  # Should not raise

    def test_under_short_limit_passes(self):
        for _ in range(RATE_LIMIT_SHORT - 1):
            _check_rate_limit("1.2.3.4")
        # Still under limit — should not raise

    def test_exceeds_short_limit_raises_429(self):
        for _ in range(RATE_LIMIT_SHORT):
            _check_rate_limit("1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit("1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_different_ips_independent(self):
        for _ in range(RATE_LIMIT_SHORT):
            _check_rate_limit("1.1.1.1")
        # Different IP should still work
        _check_rate_limit("2.2.2.2")  # Should not raise

    def test_rate_limit_constants(self):
        assert RATE_LIMIT_SHORT == 10
        assert RATE_LIMIT_LONG == 30
        assert RATE_LIMIT_DAILY == 100
        assert RATE_WINDOW_SHORT == 600
