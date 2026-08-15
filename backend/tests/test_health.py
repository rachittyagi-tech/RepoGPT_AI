"""
tests/test_health.py

Smoke tests verifying Step 2's foundation boots correctly and the
system endpoints (root, health, version) respond as expected.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from main import app


@pytest.mark.asyncio
async def test_root_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_version_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert "app_name" in body
    assert "version" in body


@pytest.mark.asyncio
async def test_request_id_header_present() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" in response.headers


@pytest.mark.asyncio
async def test_404_returns_structured_error() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert "error" in body
