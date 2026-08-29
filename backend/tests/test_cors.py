import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from config.settings import ALLOWED_ORIGINS


@pytest.mark.anyio
async def test_cors_allowed_origin():
    origin = ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "http://localhost:3000"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.headers.get("access-control-allow-origin") == origin
        assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.anyio
async def test_cors_disallowed_origin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None
