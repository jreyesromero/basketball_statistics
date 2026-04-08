"""Tests for Argon2 password helpers."""

from src.passwords import hash_password, verify_password


def test_hash_and_verify_round_trip() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password(h, "correct horse battery staple") is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("secret-one")
    assert verify_password(h, "secret-two") is False
