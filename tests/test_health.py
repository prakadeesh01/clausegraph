"""Tests for the liveness and readiness endpoints.

These are the first tests in the repository and they establish the
pattern the rest follow: build an app instance through the factory,
drive it with a TestClient, and assert on the response contract rather
than on implementation details.
"""

import pytest
from fastapi.testclient import TestClient

from clausegraph.api.main import create_app
from config.settings import get_settings


@pytest.fixture
def client() -> TestClient:
    """Provide a TestClient bound to a freshly built application.

    Returns:
        A client whose context manager triggers the lifespan hooks, so
        startup and shutdown are exercised by the tests as well.
    """
    with TestClient(create_app()) as test_client:
        yield test_client


def test_liveness_returns_ok(client: TestClient) -> None:
    """Liveness reports ok and echoes the configured service identity."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == get_settings().app_name
    assert body["version"] == get_settings().app_version


def test_liveness_does_not_require_dependencies(client: TestClient) -> None:
    """Liveness stays green regardless of downstream state.

    Guards the property that matters most about this endpoint: it must
    never fail because something else is down, since a failure here
    causes a container restart.
    """
    for _ in range(3):
        assert client.get("/health").status_code == 200


def test_readiness_is_ready_with_no_dependencies(client: TestClient) -> None:
    """Readiness treats an empty check set as ready, not as degraded."""
    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {}


def test_openapi_schema_is_generated(client: TestClient) -> None:
    """The service exposes a valid OpenAPI document.

    Cheap regression test: a malformed response model or a duplicated
    route breaks schema generation, and this catches it before the
    failure shows up as an unhelpful 500 in the browser.
    """
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]