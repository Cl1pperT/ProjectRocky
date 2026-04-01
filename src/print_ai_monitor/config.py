from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8787
    octoeverywhere_secret: str = ""
    tapo_host: str = ""
    tapo_username: str = ""
    tapo_password: str = ""
    trigger_event_types: tuple[int, ...] = (7, 8)
    power_cut_start_hour: int = 21
    power_cut_end_hour: int = 9
    dedupe_ttl_seconds: int = 900
    plug_off_retry_count: int = 2
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, dotenv_path: str | Path | None = None) -> "Settings":
        if dotenv_path is not None:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        else:
            load_dotenv(override=False)

        return cls(
            host=os.getenv("HOST", "127.0.0.1"),
            port=_int_env("PORT", 8787, minimum=1, maximum=65535),
            octoeverywhere_secret=os.getenv("OCTOEVERYWHERE_SECRET", "").strip(),
            tapo_host=os.getenv("TAPO_HOST", "").strip(),
            tapo_username=os.getenv("TAPO_USERNAME", "").strip(),
            tapo_password=os.getenv("TAPO_PASSWORD", "").strip(),
            trigger_event_types=_event_types_env(),
            power_cut_start_hour=_int_env("POWER_CUT_START_HOUR", 21, minimum=0, maximum=23),
            power_cut_end_hour=_int_env("POWER_CUT_END_HOUR", 9, minimum=0, maximum=23),
            dedupe_ttl_seconds=_int_env("DEDUPE_TTL_SECONDS", 900, minimum=1),
            plug_off_retry_count=_int_env("PLUG_OFF_RETRY_COUNT", 2, minimum=0),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )

    def is_within_power_cut_window(self, current_time: time) -> bool:
        start = self.power_cut_start_hour
        end = self.power_cut_end_hour
        hour = current_time.hour

        if start == end:
            return True
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def validate_for_server(self) -> None:
        missing = [
            name
            for name, value in (
                ("OCTOEVERYWHERE_SECRET", self.octoeverywhere_secret),
                ("TAPO_HOST", self.tapo_host),
                ("TAPO_USERNAME", self.tapo_username),
                ("TAPO_PASSWORD", self.tapo_password),
            )
            if not value
        ]
        if missing:
            raise ConfigError(f"Missing required settings: {', '.join(missing)}")

    def validate_for_probe(self) -> None:
        missing = [
            name
            for name, value in (
                ("TAPO_HOST", self.tapo_host),
                ("TAPO_USERNAME", self.tapo_username),
                ("TAPO_PASSWORD", self.tapo_password),
            )
            if not value
        ]
        if missing:
            raise ConfigError(f"Missing required settings: {', '.join(missing)}")


def _int_env(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc

    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be <= {maximum}")
    return value


def _event_types_env() -> tuple[int, ...]:
    raw_values = os.getenv("TRIGGER_EVENT_TYPES")
    if raw_values:
        values: list[int] = []
        for raw_value in raw_values.split(","):
            item = raw_value.strip()
            if not item:
                continue
            try:
                values.append(int(item))
            except ValueError as exc:
                raise ConfigError("TRIGGER_EVENT_TYPES must be a comma-separated list of integers") from exc
        if not values:
            raise ConfigError("TRIGGER_EVENT_TYPES must contain at least one event type")
        return tuple(dict.fromkeys(values))

    return (_int_env("TRIGGER_EVENT_TYPE", 8),)
