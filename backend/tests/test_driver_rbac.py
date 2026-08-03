"""Driver role cannot call Admin/Operations endpoints (direct API)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

# Representative Admin / Operations-only routes used by the portal and ops APIs.
ADMIN_GET_ENDPOINTS = [
    "/admin/dashboard",
    "/admin/locations",
    "/admin/drivers",
    "/admin/guests",
    "/admin/trips",
    "/admin/vehicles",
    "/admin/ride-requests",
]

# (path, optional JSON body — must be schema-valid so we hit auth, not 422)
ADMIN_POST_CASES: list[tuple[str, dict | None]] = [
    ("/admin/matching/batch", None),
    ("/admin/matching/queue", {"guest_id": str(uuid4())}),
    ("/admin/matching/queue/process", None),
    ("/admin/ride-requests/seed-demo", None),
    (
        "/admin/override/reassign",
        {"trip_id": str(uuid4()), "new_driver_id": str(uuid4())},
    ),
    ("/admin/override/vehicle-down", {"driver_id": str(uuid4())}),
    ("/admin/override/force-match", {"guest_id": str(uuid4()), "driver_id": str(uuid4())}),
    ("/admin/trips/match", {"guest_id": str(uuid4())}),
]


@pytest.fixture()
def client():
    """Override DB so auth rejection is tested without Postgres."""

    def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


DRIVER_HEADERS = {
    "X-Role": "driver",
    "X-Driver-Id": str(uuid4()),
    "X-User-Id": str(uuid4()),
}


@pytest.mark.parametrize("path", ADMIN_GET_ENDPOINTS)
def test_driver_forbidden_on_admin_get(client: TestClient, path: str) -> None:
    res = client.get(path, headers=DRIVER_HEADERS)
    assert res.status_code == 403, f"{path} -> {res.status_code} {res.text}"
    assert "Admin" in res.json().get("detail", "")


@pytest.mark.parametrize("path,body", ADMIN_POST_CASES)
def test_driver_forbidden_on_admin_post(client: TestClient, path: str, body: dict | None) -> None:
    res = client.post(path, headers=DRIVER_HEADERS, json=body)
    assert res.status_code == 403, f"{path} -> {res.status_code} {res.text}"
    assert "Admin" in res.json().get("detail", "")


def test_driver_forbidden_on_admin_driver_detail(client: TestClient) -> None:
    path = f"/admin/drivers/{uuid4()}"
    res = client.get(path, headers=DRIVER_HEADERS)
    assert res.status_code == 403


def test_driver_me_requires_driver_role(client: TestClient) -> None:
    """Admin token must not use driver-scoped routes."""
    res = client.get("/driver/me", headers={"X-Role": "admin", "X-Driver-Id": str(uuid4())})
    assert res.status_code == 403
    assert "Driver" in res.json().get("detail", "")


def test_driver_me_requires_driver_id_header(client: TestClient) -> None:
    res = client.get("/driver/me", headers={"X-Role": "driver"})
    assert res.status_code == 401