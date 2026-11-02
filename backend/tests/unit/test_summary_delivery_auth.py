"""Google credential refresh privacy and time ownership; no real gcloud is executed."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.summary_delivery import auth  # noqa: E402

PRIVATE = "ya29.PRIVATE_ACCESS_TOKEN_SENTINEL_0123456789"


class Clock:
    mono = 100.0
    wall = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)

    def advance(self, seconds):
        self.mono += seconds
        self.wall += timedelta(seconds=seconds)


class Gcloud:
    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.lifetime = 3600
        self.failure = None
        self.content = None
        self.token = PRIVATE
        self.elapsed = 0

    def __call__(self, argv, **kwargs):
        assert argv == ["gcloud", "config", "config-helper", "--force-auth-refresh",
                        "--format=json(credential.access_token,credential.token_expiry)", "--quiet"]
        assert PRIVATE not in repr(argv)
        assert kwargs["stdin"] == kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["stdout"] is not subprocess.PIPE and kwargs["check"] is False
        assert 0 < kwargs["timeout"] <= 15
        self.calls.append({"argv": argv, "timeout": kwargs["timeout"]})
        if self.failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=PRIVATE, stderr=PRIVATE)
        if self.failure == "oserror":
            raise OSError(PRIVATE)
        self.clock.advance(self.elapsed)
        content = self.content
        if content is None:
            content = json.dumps({"credential": {"access_token": self.token,
                "token_expiry": (self.clock.wall + timedelta(seconds=self.lifetime)).isoformat()}}).encode()
        kwargs["stdout"].write(content)
        return SimpleNamespace(returncode=1 if self.failure == "exit" else 0)


@pytest.fixture
def boundary(monkeypatch):
    clock = Clock()
    gcloud = Gcloud(clock)
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock.mono)
    monkeypatch.setattr(auth, "_utc_now", lambda: clock.wall)
    monkeypatch.setattr(auth.subprocess, "run", gcloud)
    return clock, gcloud


def get(cache, clock, *, budget=30):
    return cache.get(clock.mono + budget)


def test_constructor_and_clear_do_not_authenticate(boundary):
    _, gcloud = boundary
    cache = auth.AccessToken()
    cache.clear()
    assert not gcloud.calls and cache.refresh_count == 0


def test_fresh_token_is_reused_without_spawning_credential_process(boundary, capsys):
    clock, gcloud = boundary
    cache = auth.AccessToken()
    assert get(cache, clock) == PRIVATE
    clock.advance(60)
    assert get(cache, clock) == PRIVATE
    assert len(gcloud.calls) == cache.refresh_count == 1
    output = capsys.readouterr()
    assert PRIVATE not in output.out + output.err


def test_actual_expiry_controls_refresh_at_120_second_margin(boundary):
    clock, gcloud = boundary
    gcloud.lifetime = 300
    cache = auth.AccessToken()
    get(cache, clock)
    clock.advance(179)
    get(cache, clock)
    assert len(gcloud.calls) == 1
    clock.advance(1)
    gcloud.token = PRIVATE + "_NEXT"
    assert get(cache, clock) == gcloud.token
    assert len(gcloud.calls) == cache.refresh_count == 2


def test_explicit_clear_forces_fresh_authentication_without_replaying_any_http(boundary):
    clock, gcloud = boundary
    cache = auth.AccessToken()
    get(cache, clock)
    cache.clear()
    assert len(gcloud.calls) == 1
    gcloud.token = PRIVATE + "_NEXT"
    assert get(cache, clock) == gcloud.token
    assert len(gcloud.calls) == cache.refresh_count == 2


def test_long_reported_expiry_cannot_extend_cache_past_one_hour(boundary):
    clock, gcloud = boundary
    gcloud.lifetime = 7200
    cache = auth.AccessToken()
    get(cache, clock)
    clock.advance(3479)
    get(cache, clock)
    assert len(gcloud.calls) == 1
    clock.advance(1)
    get(cache, clock)
    assert len(gcloud.calls) == 2


@pytest.mark.parametrize("jump", [86400, -86400])
def test_cached_expiry_uses_monotonic_time_across_wall_clock_adjustments(boundary, jump):
    clock, gcloud = boundary
    cache = auth.AccessToken()
    get(cache, clock)
    clock.wall += timedelta(seconds=jump)
    clock.mono += 3479
    get(cache, clock)
    assert len(gcloud.calls) == 1
    clock.mono += 1
    get(cache, clock)
    assert len(gcloud.calls) == 2


@pytest.mark.parametrize("lifetime", [-1, 0, 119, 120])
def test_expired_or_soon_expiring_refresh_never_becomes_cached(boundary, lifetime):
    clock, gcloud = boundary
    gcloud.lifetime = lifetime
    cache = auth.AccessToken()
    with pytest.raises(auth.Refused, match="access_token_expiry_unverified"):
        get(cache, clock)
    assert cache.refresh_count == 0
    gcloud.lifetime = 3600
    assert get(cache, clock) == PRIVATE
    assert len(gcloud.calls) == 2


@pytest.mark.parametrize("content", [
    b"not JSON", b"\xff", b"[]", b"{}", b'{"credential":null}',
    b'{"credential":{"access_token":12,"token_expiry":"2026-11-02T13:00:00Z"}}',
    json.dumps({"credential": {"access_token": PRIVATE, "token_expiry": "2026-11-02T13:00:00"}}).encode(),
    json.dumps({"credential": {"access_token": PRIVATE, "token_expiry": "2026-11-02T14:00:00+01:00"}}).encode(),
    json.dumps({"credential": {"access_token": PRIVATE, "token_expiry": "invalid"}}).encode(),
    json.dumps({"credential": {"access_token": PRIVATE + "\r\nInjected:yes", "token_expiry": "2026-11-02T13:00:00Z"}}).encode(),
    b"x" * 32769,
])
def test_malformed_or_oversized_response_stays_private_and_uncached(boundary, capsys, content):
    clock, gcloud = boundary
    gcloud.content = content
    cache = auth.AccessToken()
    with pytest.raises(auth.Refused) as error:
        get(cache, clock)
    assert PRIVATE not in str(error.value) and cache.refresh_count == 0
    output = capsys.readouterr()
    assert PRIVATE not in output.out + output.err
    gcloud.content = None
    assert get(cache, clock) == PRIVATE and len(gcloud.calls) == 2


@pytest.mark.parametrize("failure", ["timeout", "oserror", "exit"])
def test_refresh_failure_clears_old_token_and_withholds_provider_error(boundary, capsys, failure):
    clock, gcloud = boundary
    cache = auth.AccessToken()
    get(cache, clock)
    clock.advance(3480)
    gcloud.failure = failure
    with pytest.raises(auth.Refused, match="access_token_refresh_failed") as error:
        get(cache, clock)
    assert PRIVATE not in str(error.value)
    assert len(gcloud.calls) == 2 and cache.refresh_count == 1
    gcloud.failure = None
    gcloud.token = PRIVATE + "_AFTER_FAILURE"
    assert get(cache, clock) == gcloud.token
    assert len(gcloud.calls) == 3 and cache.refresh_count == 2
    output = capsys.readouterr()
    assert PRIVATE not in output.out + output.err


def test_refresh_process_uses_only_remaining_request_budget(boundary):
    clock, gcloud = boundary
    assert get(auth.AccessToken(), clock, budget=2.5) == PRIVATE
    assert gcloud.calls[0]["timeout"] == 2.5


@pytest.mark.parametrize("deadline", [100.0, 99.0, float("inf"), float("nan"), True, "private"])
def test_invalid_or_exhausted_deadline_authenticates_nothing(boundary, deadline):
    _, gcloud = boundary
    with pytest.raises(auth.Refused, match="access_token_deadline"):
        auth.AccessToken().get(deadline)
    assert not gcloud.calls


def test_a_process_returning_after_deadline_cannot_supply_a_cached_credential(boundary):
    clock, gcloud = boundary
    gcloud.elapsed = 3
    cache = auth.AccessToken()
    with pytest.raises(auth.Refused, match="access_token_deadline"):
        get(cache, clock, budget=2)
    assert cache.refresh_count == 0
    gcloud.elapsed = 0
    assert get(cache, clock) == PRIVATE and len(gcloud.calls) == 2
