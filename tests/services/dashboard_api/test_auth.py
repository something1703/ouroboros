"""Unit tests for `services/dashboard_api/auth.py::get_current_user`'s email -> role
lookup, exercised directly (not via `_as`'s dependency override, which bypasses this
function entirely and can't cover it). Focus: the `DASHBOARD_DEMO_OPEN_ACCESS` fallback
added so hackathon judges can sign in with an unregistered email and still get in.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException

import services.dashboard_api.auth as auth_module
from services.dashboard_api.auth import get_current_user


@pytest.fixture(autouse=True)
def _client_id(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    yield


def _stub_claims(monkeypatch: pytest.MonkeyPatch, email: str, verified: bool = True) -> None:
    monkeypatch.setattr(
        auth_module.id_token,
        "verify_oauth2_token",
        lambda *a, **kw: {"email": email, "email_verified": verified},
    )


def test_recognized_email_gets_its_configured_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_claims(monkeypatch, "rvsrathore17@gmail.com")
    user = get_current_user(authorization="Bearer faketoken")
    assert user.role == "legal"


def test_unrecognized_email_403s_when_demo_flag_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DASHBOARD_DEMO_OPEN_ACCESS", raising=False)
    _stub_claims(monkeypatch, "judge@example.com")
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization="Bearer faketoken")
    assert exc.value.status_code == 403


@pytest.mark.parametrize("flag_value", ["1", "true", "True"])
def test_unrecognized_email_becomes_judge_when_demo_flag_set(
    monkeypatch: pytest.MonkeyPatch, flag_value: str
) -> None:
    monkeypatch.setenv("DASHBOARD_DEMO_OPEN_ACCESS", flag_value)
    _stub_claims(monkeypatch, "judge@example.com")
    user = get_current_user(authorization="Bearer faketoken")
    assert user.role == "judge"
    assert user.email == "judge@example.com"
    assert user.is_judge is True


@pytest.mark.parametrize("view_as", ["legal", "editorial", "producer"])
def test_judge_can_view_as_a_real_role(monkeypatch: pytest.MonkeyPatch, view_as: str) -> None:
    monkeypatch.setenv("DASHBOARD_DEMO_OPEN_ACCESS", "true")
    _stub_claims(monkeypatch, "judge@example.com")
    user = get_current_user(authorization="Bearer faketoken", x_view_as_role=view_as)
    assert user.role == view_as
    assert user.is_judge is True  # still flagged as a judge identity, just viewing narrower


def test_judge_view_as_ignores_an_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_DEMO_OPEN_ACCESS", "true")
    _stub_claims(monkeypatch, "judge@example.com")
    user = get_current_user(authorization="Bearer faketoken", x_view_as_role="not-a-real-role")
    assert user.role == "judge"


def test_real_user_view_as_header_has_no_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    # "View as" is a judge-only demo feature -- a real allowlisted user sending this
    # header (accidentally or otherwise) must not be able to change their own role.
    _stub_claims(monkeypatch, "iamrudra1703@gmail.com")  # real producer
    user = get_current_user(authorization="Bearer faketoken", x_view_as_role="legal")
    assert user.role == "producer"
    assert user.is_judge is False


def test_recognized_email_keeps_its_real_role_even_with_demo_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The demo flag only fills the gap for emails NOT in roles.yaml -- it must never
    # override a real configured role.
    monkeypatch.setenv("DASHBOARD_DEMO_OPEN_ACCESS", "true")
    _stub_claims(monkeypatch, "iamrudra1703@gmail.com")
    user = get_current_user(authorization="Bearer faketoken")
    assert user.role == "producer"


def test_demo_flag_does_not_bypass_email_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_DEMO_OPEN_ACCESS", "true")
    _stub_claims(monkeypatch, "judge@example.com", verified=False)
    with pytest.raises(HTTPException) as exc:
        get_current_user(authorization="Bearer faketoken")
    assert exc.value.status_code == 401
