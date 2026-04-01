from __future__ import annotations

import pytest

from print_ai_monitor.config import Settings
from print_ai_monitor.tapo import PlugControlError, TapoPlugController


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
async def test_turn_off_with_retry_succeeds_after_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = TapoPlugController(build_settings())
    attempts = {"count": 0}

    async def fake_turn_off_once() -> None:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary network failure")

    monkeypatch.setattr(controller, "_turn_off_once", fake_turn_off_once)

    used_attempts = await controller.turn_off_with_retry()

    assert used_attempts == 3
    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_turn_off_with_retry_raises_after_final_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = TapoPlugController(build_settings())

    async def fake_turn_off_once() -> None:
        raise RuntimeError("persistent failure")

    monkeypatch.setattr(controller, "_turn_off_once", fake_turn_off_once)

    with pytest.raises(PlugControlError):
        await controller.turn_off_with_retry()
