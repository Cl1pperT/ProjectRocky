from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

import uvicorn

from print_ai_monitor.config import ConfigError, Settings
from print_ai_monitor.logging_utils import setup_logging
from print_ai_monitor.tapo import PlugControlError, TapoPlugController
from print_ai_monitor.web import create_app


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        settings = Settings.from_env()
        setup_logging(settings.log_level)

        if args.command == "serve":
            settings.validate_for_server()
            app = create_app(settings)
            uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
            return

        if args.command == "probe-plug":
            settings.validate_for_probe()
            result = asyncio.run(TapoPlugController(settings).probe())
            print(json.dumps(asdict(result), sort_keys=True))
            return
    except (ConfigError, PlugControlError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print AI Monitor service")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("serve", help="Run the webhook service")
    subparsers.add_parser("probe-plug", help="Verify TAPO plug connectivity")
    return parser
