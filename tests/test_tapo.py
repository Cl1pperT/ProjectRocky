from __future__ import annotations

import pytest

from print_ai_monitor.config import Settings
from print_ai_monitor.tapo import PlugControlError, TapoPlugController


def build_settings() -> Settings:
    return Settings(
        octoeverywhere_secret="super-secret",
        tapo_host="192.168.1.25",
        tapo_alias="",
        tapo_username="user@example.com",
        tapo_password="pass",
        trigger_event_types=(7, 8),
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


@pytest.mark.asyncio
async def test_toggle_switches_from_off_to_on(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = TapoPlugController(build_settings())

    class FakeDevice:
        def __init__(self) -> None:
            self.host = "192.168.1.25"
            self.alias = "Test Plug"
            self.is_on = False
            self.disconnected = False

        async def update(self) -> None:
            return None

        async def turn_on(self) -> None:
            self.is_on = True

        async def turn_off(self) -> None:
            self.is_on = False

        async def disconnect(self) -> None:
            self.disconnected = True

    fake_device = FakeDevice()

    async def fake_discover_single(*args, **kwargs) -> FakeDevice:
        return fake_device

    monkeypatch.setattr("print_ai_monitor.tapo.Discover.discover_single", fake_discover_single)

    result = await controller.toggle()

    assert result.before is False
    assert result.after is True
    assert result.alias == "Test Plug"
    assert fake_device.disconnected is True


@pytest.mark.asyncio
async def test_probe_can_resolve_case_insensitive_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = TapoPlugController(
        Settings(
            octoeverywhere_secret="super-secret",
            tapo_host="",
            tapo_alias="printer",
            tapo_username="user@example.com",
            tapo_password="pass",
            trigger_event_types=(7, 8),
            dedupe_ttl_seconds=60,
            plug_off_retry_count=2,
        )
    )

    class FakeDevice:
        def __init__(self, host: str, alias: str, is_on: bool) -> None:
            self.host = host
            self.alias = alias
            self.is_on = is_on
            self.disconnected = False

        async def update(self) -> None:
            return None

        async def disconnect(self) -> None:
            self.disconnected = True

    printer = FakeDevice("192.168.1.25", "Printer", True)
    other = FakeDevice("192.168.1.99", "Lamp", False)

    async def fake_discover(*args, **kwargs):
        return {printer.host: printer, other.host: other}

    monkeypatch.setattr("print_ai_monitor.tapo.Discover.discover", fake_discover)

    result = await controller.probe()

    assert result.host == "192.168.1.25"
    assert result.alias == "Printer"
    assert result.is_on is True
    assert other.disconnected is True


@pytest.mark.asyncio
async def test_probe_raises_if_alias_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = TapoPlugController(
        Settings(
            octoeverywhere_secret="super-secret",
            tapo_host="",
            tapo_alias="printer",
            tapo_username="user@example.com",
            tapo_password="pass",
            trigger_event_types=(7, 8),
            dedupe_ttl_seconds=60,
            plug_off_retry_count=2,
        )
    )

    class FakeDevice:
        def __init__(self, host: str, alias: str) -> None:
            self.host = host
            self.alias = alias

        async def update(self) -> None:
            return None

        async def disconnect(self) -> None:
            return None

    async def fake_discover(*args, **kwargs):
        return {"192.168.1.99": FakeDevice("192.168.1.99", "Lamp")}

    monkeypatch.setattr("print_ai_monitor.tapo.Discover.discover", fake_discover)

    with pytest.raises(PlugControlError, match="alias"):
        await controller.probe()
