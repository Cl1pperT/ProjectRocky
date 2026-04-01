from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from print_ai_monitor.config import Settings
from print_ai_monitor.dedupe import PrintDeduper
from print_ai_monitor.service import WebhookService
from print_ai_monitor.tapo import TapoPlugController


def create_app(
    settings: Settings,
    plug_controller: TapoPlugController | None = None,
    deduper: PrintDeduper | None = None,
) -> FastAPI:
    service = WebhookService(
        settings=settings,
        plug_controller=plug_controller or TapoPlugController(settings),
        deduper=deduper,
    )

    app = FastAPI(title="Print AI Monitor", version="0.1.0")

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhook/octoeverywhere")
    async def octoeverywhere_webhook(request: Request) -> JSONResponse:
        try:
            body: Any = await request.json()
        except json.JSONDecodeError:
            return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

        if not isinstance(body, dict):
            return JSONResponse(status_code=400, content={"detail": "JSON object required"})

        response = await service.handle_payload(body)
        return JSONResponse(status_code=response.status_code, content=response.payload)

    return app
