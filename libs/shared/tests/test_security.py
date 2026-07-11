import uuid

import jwt
import pytest

from shared.security import decode_token, encode_token

SEC = "test-secret-value-at-least-32-chars-long"
AUD = "fastapi-users:auth"


def test_roundtrip_claims():
    uid = uuid.uuid4()
    token = encode_token(
        user_id=uid, secret=SEC, audience=AUD, lifetime_seconds=60,
        email="x@y.z", is_superuser=True,
    )
    p = decode_token(token, secret=SEC, audience=AUD)
    assert p.id == uid and p.email == "x@y.z" and p.is_superuser is True


def test_wrong_secret_rejected():
    token = encode_token(user_id=uuid.uuid4(), secret=SEC, audience=AUD, lifetime_seconds=60)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, secret="another-secret", audience=AUD)


def test_expired_rejected():
    token = encode_token(
        user_id=uuid.uuid4(), secret=SEC, audience=AUD, lifetime_seconds=-1, now=1_000_000
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, secret=SEC, audience=AUD)


def test_wrong_audience_rejected():
    token = encode_token(user_id=uuid.uuid4(), secret=SEC, audience="other", lifetime_seconds=60)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, secret=SEC, audience=AUD)
