"""Owner sign-in protects the Control Center; agents and health checks are unaffected."""

import pytest

from app.config import get_settings
from app.services import owner_auth


@pytest.fixture
def owner_password(monkeypatch):
    monkeypatch.setattr(get_settings(), "OWNER_PASSWORD", "correct horse battery staple")
    owner_auth.throttle._fails.clear()
    yield "correct horse battery staple"
    owner_auth.throttle._fails.clear()


def test_open_when_no_password_is_set(client, sample_mandate):
    assert client.get("/api/mandates").status_code == 200
    assert client.get("/api/owner/session").json() == {"auth_enabled": False, "authenticated": True, "misconfigured": False}


def test_owner_routes_require_sign_in(client, sample_mandate, owner_password):
    for method, path in [("get", "/api/mandates"), ("get", "/api/proposals"), ("get", "/api/agents"),
                         ("post", "/api/agents"), ("get", "/api/audit"), ("post", "/api/proposals/x/approve"),
                         ("post", "/api/payments/x/capture"), ("put", f"/api/mandates/{sample_mandate.id}")]:
        res = getattr(client, method)(path)
        assert res.status_code == 401, (path, res.status_code)
        assert res.json()["detail"]["code"] == "OWNER_AUTH_REQUIRED"
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/status").status_code == 200


def test_sign_in_sets_httponly_cookie_and_unlocks(client, sample_mandate, owner_password):
    assert client.post("/api/owner/login", json={"password": "wrong"}).status_code == 401
    res = client.post("/api/owner/login", json={"password": owner_password})
    assert res.status_code == 200 and res.json()["authenticated"] is True
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and owner_password not in cookie
    assert client.get("/api/mandates").status_code == 200
    assert client.get("/api/owner/session").json()["authenticated"] is True
    client.post("/api/owner/logout")
    assert client.get("/api/mandates").status_code == 401


def test_forged_or_expired_tokens_are_rejected(owner_password):
    good = owner_auth.issue_token()
    assert owner_auth.token_valid(good)
    expiry, sig = good.split(".")
    assert not owner_auth.token_valid(f"{int(expiry) + 999}.{sig}")
    assert not owner_auth.token_valid("garbage")
    assert not owner_auth.token_valid(owner_auth.issue_token(now=0))


def test_failed_logins_are_throttled(client, owner_password):
    for _ in range(5):
        assert client.post("/api/owner/login", json={"password": "nope"}).status_code == 401
    assert client.post("/api/owner/login", json={"password": owner_password}).status_code == 429


def test_agents_use_their_own_keys_not_the_owner_session(client, sample_mandate, owner_password):
    client.post("/api/owner/login", json={"password": owner_password})
    key = client.post("/api/agents", json={"name": "Agent A", "mandate_ids": [sample_mandate.id]}).json()["api_key"]
    client.post("/api/owner/logout")
    assert client.get("/api/agent/v1/whoami", headers={"Authorization": f"Bearer {key}"}).status_code == 200


def test_required_but_unconfigured_fails_closed(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "REQUIRE_OWNER_AUTH", True)
    res = client.get("/api/mandates")
    assert res.status_code == 503 and res.json()["detail"]["code"] == "OWNER_AUTH_NOT_CONFIGURED"
    assert client.get("/api/owner/session").json()["misconfigured"] is True
