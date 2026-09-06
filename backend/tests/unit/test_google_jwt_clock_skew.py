"""Google id-token validation tolerates configured skew with actual offline RSA tokens."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from app.services import oauth_verify


@pytest.mark.asyncio
async def test_google_id_token_accepts_only_configured_future_iat_skew(monkeypatch):
    now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public_jwk["kid"] = "google-test-key"
    get_jwks = AsyncMock(return_value={"keys": [public_jwk]})
    monkeypatch.setattr(oauth_verify, "_get_google_jwks", get_jwks)
    monkeypatch.setattr(oauth_verify.settings, "GOOGLE_CLIENT_ID", "offline-google-client")
    monkeypatch.setattr(oauth_verify.settings, "JWT_LEEWAY_SECONDS", 10)
    monkeypatch.setattr(jwt.api_jwt, "datetime", FrozenDatetime)

    claims = {
        "sub": "google-subject",
        "iss": "https://accounts.google.com",
        "aud": "offline-google-client",
        "exp": int(now.timestamp()) + 300,
        "iat": int(now.timestamp()) + 5,
    }
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": public_jwk["kid"]})
    assert await oauth_verify._verify_google_id_token(token) == claims
    get_jwks.assert_awaited_once_with()

    outside_leeway = {**claims, "iat": int(now.timestamp()) + 11}
    token = jwt.encode(outside_leeway, key, algorithm="RS256", headers={"kid": public_jwk["kid"]})
    with pytest.raises(ValueError, match=r"Google id_token invalid:.*not yet valid.*iat"):
        await oauth_verify._verify_google_id_token(token)
