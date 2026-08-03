"""Guest role cannot call Admin or Driver endpoints (direct API)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

ADMIN_GET = [
    "/admin/dashboard",
    "/admin/drivers",
    "/admin/guests",
    "/admin/trips",
    "/admin/ride-requests",
]

DRIVER_GET = ["/driver/me", "/driver/trip"]


@pytest.fixture()
def client():
    def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


GUEST_HEADERS = {
    "X-Role": "guest",
    "X-Guest-Id": str(uuid4()),
    "X-User-Id": str(uuid4()),
}


@pytest.mark.parametrize("path", ADMIN_GET)
def test_guest_forbidden_on_admin(client: TestClient, path: str) -> None:
    res = client.get(path, headers=GUEST_HEADERS)
    assert res.status_code == 403
    assert "Admin" in res.json().get("detail", "")


@pytest.mark.parametrize("path", DRIVER_GET)
def test_guest_forbidden_on_driver(client: TestClient, path: str) -> None:
    res = client.get(path, headers=GUEST_HEADERS)
    assert res.status_code == 403


def test_guest_me_requires_guest_role(client: TestClient) -> None:
    res = client.get("/guest/me", headers={"X-Role": "admin", "X-Guest-Id": str(uuid4())})
    assert res.status_code == 403
    assert "Guest" in res.json().get("detail", "")


def test_guest_me_requires_guest_id(client: TestClient) -> None:
    res = client.get("/guest/me", headers={"X-Role": "guest"})
    assert res.status_code == 401


def test_guest_cannot_list_admin_drivers(client: TestClient) -> None:
    res = client.get("/admin/drivers", headers=GUEST_HEADERS)
    assert res.status_code == 403
