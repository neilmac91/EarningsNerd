"""Deadline-owned Google credential refresh; no authentication occurs at import or construction."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import re
import subprocess
import tempfile
import time

from ops.summary_delivery.spec import Refused

COMMAND = (
    "gcloud", "config", "config-helper", "--force-auth-refresh",
    "--format=json(credential.access_token,credential.token_expiry)", "--quiet",
)
MAX_OUTPUT_BYTES = 32768
REFRESH_MARGIN_SECONDS = 120
MAX_CACHE_SECONDS = 3600


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _refuse(reason: str) -> None:
    raise Refused(reason) from None


class AccessToken:
    """Cache only until a monotonic refresh threshold derived from actual UTC expiry.

    The controller owns the HTTP operation: this helper never retries requests or
    mutations. Provider stdout/stderr, tokens and command errors never leave it.
    """

    def __init__(self) -> None:
        self._token = ""
        self._refresh_at = 0.0
        self.refresh_count = 0

    def clear(self) -> None:
        self._token = ""
        self._refresh_at = 0.0

    def get(self, deadline: float) -> str:
        now = time.monotonic()
        if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
                or not math.isfinite(deadline) or deadline <= now):
            self.clear()
            _refuse("access_token_deadline")
        if self._token and now < self._refresh_at:
            return self._token
        self.clear()  # A failed refresh must never fall back to the old credential.
        try:
            with tempfile.TemporaryFile() as output:
                result = subprocess.run(
                    list(COMMAND), stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                    timeout=min(15, deadline - now), check=False,
                )
                if result.returncode != 0:
                    _refuse("access_token_refresh_failed")
                if time.monotonic() >= deadline:
                    _refuse("access_token_deadline")
                output.seek(0)
                content = output.read(MAX_OUTPUT_BYTES + 1)
            if len(content) > MAX_OUTPUT_BYTES:
                _refuse("access_token_reply_bound")
            response = json.loads(content)
            credential = response.get("credential") if isinstance(response, dict) else None
            if not isinstance(credential, dict):
                _refuse("access_token_reply_unverified")
            token, timestamp = credential.get("access_token"), credential.get("token_expiry")
            if (not isinstance(token, str) or not 1 <= len(token) <= 16384
                    or not re.fullmatch(r"[A-Za-z0-9._~+/\-]+=*", token) or not isinstance(timestamp, str)):
                _refuse("access_token_reply_unverified")
            expiry = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry.utcoffset() != timedelta(0):
                _refuse("access_token_expiry_unverified")
            lifetime = (expiry - _utc_now()).total_seconds()
            if lifetime <= REFRESH_MARGIN_SECONDS:
                _refuse("access_token_expiry_unverified")
            now = time.monotonic()
            if now >= deadline:
                _refuse("access_token_deadline")
            self._token = token
            self._refresh_at = now + min(lifetime, MAX_CACHE_SECONDS) - REFRESH_MARGIN_SECONDS
            self.refresh_count += 1
            return token
        except Refused:
            self.clear()
            raise
        except (subprocess.SubprocessError, OSError, ValueError, TypeError, UnicodeError, OverflowError):
            self.clear()
            _refuse("access_token_refresh_failed")
