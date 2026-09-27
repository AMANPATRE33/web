"""Smoke test for the application factory, health probes and error envelope.

Run with the API's dependencies installed; requires a reachable DATABASE_URL
because the readiness probe checks it for real.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["api"] == "/api/v1"
    assert "version" in body


@pytest.mark.anyio
async def test_request_id_header_present(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers.get("X-Request-ID")


@pytest.mark.anyio
async def test_security_headers(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


@pytest.mark.anyio
async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/definitely-not-a-route")
    assert response.status_code == 404
    body = response.json()
    assert set(body["error"]) >= {"code", "message"}
    assert body["error"]["code"] == "not_found"


@pytest.mark.anyio
async def test_api_index(client: AsyncClient) -> None:
    response = await client.get("/api/v1/")
    assert response.status_code == 200
    assert "resources" in response.json()
