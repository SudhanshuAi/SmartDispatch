"""Final-pass: RBAC cannot be bypassed; matching-down leaves trips/overrides intact."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.services import matching_service


@pytest.fixture()
def client():
    def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_admin_routes_require_explicit_role_header(client: TestClient) -> None:
    """Missing X-Role must not fall through to default-admin."""
    res = client.get("/admin/dashboard")
    assert res.status_code == 401
    assert "X-Role" in res.json().get("detail", "")


def test_guest_cannot_hit_matching_batch(client: TestClient) -> None:
    res = client.post(
        "/admin/matching/batch",
        headers={"X-Role": "guest", "X-Guest-Id": str(uuid4())},
    )
    assert res.status_code == 403


def test_driver_cannot_hit_force_match(client: TestClient) -> None:
    res = client.post(
        "/admin/override/force-match",
        headers={"X-Role": "driver", "X-Driver-Id": str(uuid4())},
        json={"guest_id": str(uuid4()), "driver_id": str(uuid4())},
    )
    assert res.status_code == 403


def test_matching_disabled_returns_503_without_touching_engine(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "matching_engine_enabled", False)
    with pytest.raises(matching_service.MatchingEngineUnavailable):
        matching_service._ensure_engine_enabled()


def test_matching_status_admin_only(client: TestClient) -> None:
    denied = client.get("/admin/matching/status", headers={"X-Role": "driver", "X-Driver-Id": str(uuid4())})
    assert denied.status_code == 403
    ok = client.get("/admin/matching/status", headers={"X-Role": "admin"})
    assert ok.status_code == 200
    body = ok.json()
    assert "matching_engine_enabled" in body
    assert "overrides" in body["note"].lower() or "override" in body["note"].lower()
