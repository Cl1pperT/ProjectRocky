from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from hmac import compare_digest
from typing import Any, Callable

from print_ai_monitor.config import Settings
from print_ai_monitor.dedupe import PrintDeduper
from print_ai_monitor.logging_utils import log_event
from print_ai_monitor.tapo import PlugControlError, TapoPlugController


@dataclass(frozen=True, slots=True)
class ServiceResponse:
    status_code: int
    payload: dict[str, Any]


class WebhookService:
    def __init__(
        self,
        settings: Settings,
        plug_controller: TapoPlugController,
        deduper: PrintDeduper | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._plug_controller = plug_controller
        self._deduper = deduper or PrintDeduper(settings.dedupe_ttl_seconds)
        self._logger = logging.getLogger(__name__)
        self._now_provider = now_provider or datetime.now

    async def handle_payload(self, payload: dict[str, Any]) -> ServiceResponse:
        event_type = payload.get("EventType")
        secret_key = payload.get("SecretKey")
        print_id = _optional_str(payload.get("PrintId"))

        if not isinstance(event_type, int):
            return ServiceResponse(400, {"detail": "EventType must be an integer"})
        if not isinstance(secret_key, str) or not secret_key:
            return ServiceResponse(400, {"detail": "SecretKey is required"})

        log_event(
            self._logger,
            logging.INFO,
            "webhook_received",
            event_type=event_type,
            print_id=print_id,
        )

        if not compare_digest(secret_key, self._settings.octoeverywhere_secret):
            log_event(
                self._logger,
                logging.WARNING,
                "webhook_validation_failed",
                reason="secret_mismatch",
                event_type=event_type,
                print_id=print_id,
            )
            return ServiceResponse(401, {"detail": "Invalid secret"})

        if event_type not in self._settings.trigger_event_types:
            log_event(
                self._logger,
                logging.INFO,
                "webhook_ignored",
                reason="event_type",
                event_type=event_type,
                print_id=print_id,
                accepted_event_types=self._settings.trigger_event_types,
            )
            return ServiceResponse(200, {"status": "ignored", "reason": "event_type"})

        current_time = self._now_provider().time()
        if not self._settings.is_within_power_cut_window(current_time):
            log_event(
                self._logger,
                logging.INFO,
                "webhook_ignored",
                reason="outside_power_cut_window",
                event_type=event_type,
                print_id=print_id,
                power_cut_start_hour=self._settings.power_cut_start_hour,
                power_cut_end_hour=self._settings.power_cut_end_hour,
            )
            return ServiceResponse(200, {"status": "ignored", "reason": "outside_power_cut_window"})

        if print_id and not self._deduper.try_mark(print_id):
            log_event(
                self._logger,
                logging.INFO,
                "webhook_ignored",
                reason="duplicate_print_id",
                event_type=event_type,
                print_id=print_id,
            )
            return ServiceResponse(200, {"status": "ignored", "reason": "duplicate_print_id"})

        try:
            attempts = await self._plug_controller.turn_off_with_retry()
        except PlugControlError as exc:
            if print_id:
                self._deduper.clear(print_id)
            log_event(
                self._logger,
                logging.ERROR,
                "plug_off_failed",
                event_type=event_type,
                print_id=print_id,
                error=str(exc),
            )
            return ServiceResponse(502, {"detail": "Failed to turn off plug"})

        log_event(
            self._logger,
            logging.INFO,
            "plug_off_succeeded",
            event_type=event_type,
            print_id=print_id,
            attempts=attempts,
        )
        return ServiceResponse(200, {"status": "success", "action": "plug_off"})


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
