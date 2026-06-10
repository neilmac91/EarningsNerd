"""Tests for the anonymous (guest) daily summary quota (roadmap S5)."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services import guest_quota


@pytest.mark.asyncio
async def test_fails_open_when_redis_unavailable():
    with patch.object(guest_quota, "get_redis_client", new=AsyncMock(return_value=None)):
        allowed, count = await guest_quota.check_and_increment_guest_quota("1.2.3.4", 3)
    assert allowed is True and count == 0


@pytest.mark.asyncio
async def test_first_summary_is_always_allowed_and_sets_expiry():
    fake = AsyncMock()
    fake.incr = AsyncMock(return_value=1)
    fake.expire = AsyncMock()
    with patch.object(guest_quota, "get_redis_client", new=AsyncMock(return_value=fake)):
        allowed, count = await guest_quota.check_and_increment_guest_quota("1.2.3.4", 3)
    assert allowed is True and count == 1
    fake.expire.assert_awaited_once()  # rolling daily expiry set on first hit


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_blocks():
    fake = AsyncMock()
    fake.expire = AsyncMock()
    # Within limit (3rd of the day) is allowed; the 4th is blocked.
    fake.incr = AsyncMock(return_value=3)
    with patch.object(guest_quota, "get_redis_client", new=AsyncMock(return_value=fake)):
        allowed, count = await guest_quota.check_and_increment_guest_quota("1.2.3.4", 3)
    assert allowed is True and count == 3

    fake.incr = AsyncMock(return_value=4)
    with patch.object(guest_quota, "get_redis_client", new=AsyncMock(return_value=fake)):
        allowed, count = await guest_quota.check_and_increment_guest_quota("1.2.3.4", 3)
    assert allowed is False and count == 4


@pytest.mark.asyncio
async def test_fails_open_on_redis_error():
    fake = AsyncMock()
    fake.incr = AsyncMock(side_effect=RuntimeError("redis down"))
    with patch.object(guest_quota, "get_redis_client", new=AsyncMock(return_value=fake)):
        allowed, count = await guest_quota.check_and_increment_guest_quota("1.2.3.4", 3)
    assert allowed is True and count == 0
