from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import NotAuthenticated
from app.utils import (
    decode_access_token,
    generate_access_token,
    generate_verification_code,
    hash_verification_code,
    is_valid_verification_code,
)


def test_verification_code_is_six_digits():
    for _ in range(100):
        code = generate_verification_code()
        assert len(code) == 6
        assert code.isdigit()


def test_correct_code_is_valid():
    shipment_id = uuid4()
    stored_hash = hash_verification_code(shipment_id, "123456")

    assert is_valid_verification_code(shipment_id, "123456", stored_hash)


@pytest.mark.parametrize("wrong_code", ["123457", "000000", "", "1234567"])
def test_wrong_code_is_invalid(wrong_code):
    shipment_id = uuid4()
    stored_hash = hash_verification_code(shipment_id, "123456")

    assert not is_valid_verification_code(shipment_id, wrong_code, stored_hash)


def test_code_only_works_for_its_shipment():
    stored_hash = hash_verification_code(uuid4(), "123456")

    assert not is_valid_verification_code(uuid4(), "123456", stored_hash)


def test_access_token_round_trip():
    token = generate_access_token({"user": {"name": "Seller", "id": "abc"}})

    data = decode_access_token(token)

    assert data is not None
    assert data["user"] == {"name": "Seller", "id": "abc"}
    # Each token gets a unique id, logout puts it on the blacklist
    assert "jti" in data


def test_each_token_has_a_different_jti():
    first = decode_access_token(generate_access_token({}))
    second = decode_access_token(generate_access_token({}))

    assert first is not None and second is not None
    assert first["jti"] != second["jti"]


def test_expired_token_raises():
    token = generate_access_token({}, expiry=timedelta(seconds=-1))

    with pytest.raises(NotAuthenticated, match="Token expired"):
        decode_access_token(token)


@pytest.mark.parametrize("bad_token", ["not-a-token", "a.b.c", ""])
def test_invalid_token_returns_none(bad_token):
    assert decode_access_token(bad_token) is None


def test_token_with_changed_data_returns_none():
    # A token has 3 parts: header.payload.signature
    header, _, signature = generate_access_token({"user": {"id": "abc"}}).split(".")
    # Someone puts another user's data in the token but keeps the signature
    _, other_payload, _ = generate_access_token({"user": {"id": "xyz"}}).split(".")

    assert decode_access_token(f"{header}.{other_payload}.{signature}") is None
