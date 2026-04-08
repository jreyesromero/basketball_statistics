"""Tests for admin route validation helpers (no database)."""

from src.admin_routes import _plausible_email


def test_plausible_email_accepts_simple_address() -> None:
    assert _plausible_email("user@example.com") is True


def test_plausible_email_rejects_no_at() -> None:
    assert _plausible_email("notanemail") is False


def test_plausible_email_rejects_no_domain_dot() -> None:
    assert _plausible_email("a@b") is False


def test_plausible_email_rejects_space() -> None:
    assert _plausible_email("bad @x.com") is False


def test_plausible_email_strips_whitespace() -> None:
    assert _plausible_email("  user@example.com  ") is True
