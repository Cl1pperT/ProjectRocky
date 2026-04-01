from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from print_ai_monitor.config import Settings
from print_ai_monitor.dedupe import PrintDeduper
from print_ai_monitor.service import WebhookService
from print_ai_monitor.tapo import PlugControlError


@dataclass
class FakePlugController:
    attempts_before_success: int = 1
    calls: int = 0

    async def turn_off_with_retry(self) -> int:
        self.calls += 1
        if self.calls < self.attempts_before_success:
            raise PlugControlError("simulated failure")
        return self.calls


def build_settings() -> Settings:
    return Settings(
        octoeverywhere_secret="super-secret",
        tapo_host="192.168.1.25",
        tapo_username="user@example.com",
        tapo_password="pass",
        trigger_event_types=(7, 8),
        power_cut_start_hour=21,
        power_cut_end_hour=9,
        dedupe_ttl_seconds=60,
        plug_off_retry_count=2,
    )


@pytest.mark.asyncio
async def test_secret_validation_rejects_wrong_secret() -> None:
    service = WebhookService(
        build_settings(),
        FakePlugController(),
        now_provider=lambda: datetime(2026, 3, 31, 22, 0, 0),
    )
    response = await service.handle_payload({"EventType": 8, "SecretKey": "wrong"})
    assert response.status_code == 401
    assert response.payload == {"detail": "Invalid secret"}


@pytest.mark.asyncio
async def test_ignores_non_trigger_event() -> None:
    plug = FakePlugController()
    service = WebhookService(
        build_settings(),
        plug,
        now_provider=lambda: datetime(2026, 3, 31, 22, 0, 0),
    )
    response = await service.handle_payload({"EventType": 3, "SecretKey": "super-secret"})
    assert response.status_code == 200
    assert response.payload == {"status": "ignored", "reason": "event_type"}
    assert plug.calls == 0


@pytest.mark.asyncio
async def test_event_type_7_triggers_power_cut() -> None:
    plug = FakePlugController()
    service = WebhookService(
        build_settings(),
        plug,
        now_provider=lambda: datetime(2026, 3, 31, 22, 0, 0),
    )
    response = await service.handle_payload({"EventType": 7, "SecretKey": "super-secret"})
    assert response.status_code == 200
    assert response.payload == {"status": "success", "action": "plug_off"}
    assert plug.calls == 1


@pytest.mark.asyncio
async def test_trigger_is_ignored_outside_power_cut_window() -> None:
    plug = FakePlugController()
    service = WebhookService(
        build_settings(),
        plug,
        now_provider=lambda: datetime(2026, 4, 1, 14, 0, 0),
    )
    response = await service.handle_payload({"EventType": 8, "SecretKey": "super-secret"})
    assert response.status_code == 200
    assert response.payload == {"status": "ignored", "reason": "outside_power_cut_window"}
    assert plug.calls == 0


@pytest.mark.asyncio
async def test_duplicate_print_id_is_suppressed() -> None:
    plug = FakePlugController()
    service = WebhookService(
        build_settings(),
        plug,
        deduper=PrintDeduper(ttl_seconds=600),
        now_provider=lambda: datetime(2026, 3, 31, 22, 0, 0),
    )
    payload = {"EventType": 8, "SecretKey": "super-secret", "PrintId": "print-123"}

    first = await service.handle_payload(payload)
    second = await service.handle_payload(payload)

    assert first.status_code == 200
    assert first.payload == {"status": "success", "action": "plug_off"}
    assert second.status_code == 200
    assert second.payload == {"status": "ignored", "reason": "duplicate_print_id"}
    assert plug.calls == 1


@pytest.mark.asyncio
async def test_failed_trigger_clears_dedupe_marker_for_retry() -> None:
    plug = FakePlugController(attempts_before_success=99)
    service = WebhookService(
        build_settings(),
        plug,
        deduper=PrintDeduper(ttl_seconds=600),
        now_provider=lambda: datetime(2026, 3, 31, 22, 0, 0),
    )
    payload = {"EventType": 8, "SecretKey": "super-secret", "PrintId": "print-456"}

    first = await service.handle_payload(payload)
    second = await service.handle_payload(payload)

    assert first.status_code == 502
    assert second.status_code == 502
    assert plug.calls == 2
