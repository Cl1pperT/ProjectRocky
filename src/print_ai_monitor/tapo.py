from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from kasa import Discover

from print_ai_monitor.config import Settings
from print_ai_monitor.logging_utils import log_event


class PlugControlError(RuntimeError):
    """Raised when the TAPO plug could not be controlled."""


@dataclass(frozen=True, slots=True)
class PlugProbeResult:
    host: str
    alias: str | None
    is_on: bool


class TapoPlugController:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(__name__)

    async def probe(self) -> PlugProbeResult:
        device = await Discover.discover_single(
            self._settings.tapo_host,
            username=self._settings.tapo_username,
            password=self._settings.tapo_password,
        )
        if device is None:
            raise PlugControlError(f"No TAPO device discovered at {self._settings.tapo_host}")

        try:
            await device.update()
            return PlugProbeResult(
                host=device.host,
                alias=device.alias,
                is_on=device.is_on,
            )
        finally:
            await device.disconnect()

    async def turn_off_with_retry(self) -> int:
        attempts = self._settings.plug_off_retry_count + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                await self._turn_off_once()
                return attempt
            except Exception as exc:
                last_error = exc
                log_event(
                    self._logger,
                    logging.WARNING if attempt < attempts else logging.ERROR,
                    "plug_off_attempt_failed",
                    attempt=attempt,
                    max_attempts=attempts,
                    host=self._settings.tapo_host,
                    error=str(exc),
                )
                if attempt >= attempts:
                    break
                await asyncio.sleep(min(0.5 * attempt, 2.0))

        message = f"Failed to turn off TAPO plug at {self._settings.tapo_host}"
        if last_error is not None:
            raise PlugControlError(message) from last_error
        raise PlugControlError(message)

    async def _turn_off_once(self) -> None:
        device = await Discover.discover_single(
            self._settings.tapo_host,
            username=self._settings.tapo_username,
            password=self._settings.tapo_password,
        )
        if device is None:
            raise PlugControlError(f"No TAPO device discovered at {self._settings.tapo_host}")

        try:
            await device.update()
            await device.turn_off()
        finally:
            await device.disconnect()
