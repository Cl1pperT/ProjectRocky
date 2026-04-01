from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict

from print_ai_monitor.config import ConfigError, Settings
from print_ai_monitor.logging_utils import setup_logging
from print_ai_monitor.tapo import PlugControlError, TapoPlugController


def main() -> None:
    try:
        settings = Settings.from_env()
        settings.validate_for_probe()
        setup_logging(settings.log_level)

        result = asyncio.run(TapoPlugController(settings).toggle())
        print(json.dumps(asdict(result), sort_keys=True))
    except (ConfigError, PlugControlError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
