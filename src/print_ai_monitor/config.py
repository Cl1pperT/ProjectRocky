from __future__ import annotations

import os
from dataclasses import dataclass
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
    trigger_event_type: int = 8
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
            trigger_event_type=_int_env("TRIGGER_EVENT_TYPE", 8),
            dedupe_ttl_seconds=_int_env("DEDUPE_TTL_SECONDS", 900, minimum=1),
            plug_off_retry_count=_int_env("PLUG_OFF_RETRY_COUNT", 2, minimum=0),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )

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
