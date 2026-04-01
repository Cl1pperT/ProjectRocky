from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

from print_ai_monitor.config import Settings
from print_ai_monitor.web import create_app


@dataclass
class FakePlugController:
    calls: int = 0

    async def turn_off_with_retry(self) -> int:
        self.calls += 1
        return self.calls


def build_settings() -> Settings:
    return Settings(
        octoeverywhere_secret="super-secret",
        tapo_host="192.168.1.25",
        tapo_username="user@example.com",
        tapo_password="pass",
        trigger_event_type=8,
        dedupe_ttl_seconds=60,
        plug_off_retry_count=2,
    )


@pytest.mark.asyncio
async def test_healthcheck() -> None:
    app = create_app(build_settings(), plug_controller=FakePlugController())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_webhook_accepts_valid_trigger() -> None:
    plug = FakePlugController()
    app = create_app(build_settings(), plug_controller=plug)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/webhook/octoeverywhere",
            json={"EventType": 8, "PrintId": "print-1", "SecretKey": "super-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "action": "plug_off"}
    assert plug.calls == 1


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret() -> None:
    app = create_app(build_settings(), plug_controller=FakePlugController())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/webhook/octoeverywhere",
            json={"EventType": 8, "SecretKey": "wrong"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid secret"}


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_json() -> None:
    app = create_app(build_settings(), plug_controller=FakePlugController())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/webhook/octoeverywhere",
            content="{not-json",
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid JSON"}


@pytest.mark.asyncio
async def test_webhook_ignores_non_trigger_events() -> None:
    plug = FakePlugController()
    app = create_app(build_settings(), plug_controller=plug)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/webhook/octoeverywhere",
            json={"EventType": 3, "SecretKey": "super-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "reason": "event_type"}
    assert plug.calls == 0
