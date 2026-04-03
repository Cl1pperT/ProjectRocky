# Print AI Monitor

`print-ai-monitor` runs on a Raspberry Pi and listens for OctoEverywhere webhook events. When OctoEverywhere reports `EventType=7` (`Gadget Possible Failure Warning`) or `EventType=8` (`Gadget Paused Print Due To Failure`) during the configured overnight window, the service turns off a TAPO P125M smart plug over the local network.

## What It Does

- Exposes `POST /webhook/octoeverywhere` for OctoEverywhere LAN webhooks.
- Exposes `GET /healthz` for liveness checks.
- Authenticates webhook payloads with a shared secret.
- Ignores all events except the configured trigger event types.
- Only cuts power during the configured quiet hours, which default to 9 PM through 9 AM.
- Suppresses duplicate shutdown attempts for the same `PrintId`.
- Retries local TAPO power-off requests on transient failures.

## Requirements

- Raspberry Pi Zero 2 W or better
- Python 3.11+
- OctoEverywhere already installed
- TAPO P125M already paired to your LAN and reachable by alias or IP
- The Pi must stay on separate power from the printer plug

## Install

```bash
cd /opt/print-ai-monitor
uv venv
. .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` and set:

- `OCTOEVERYWHERE_SECRET`
- `TAPO_ALIAS=Printer`
- `TAPO_HOST` as an optional fallback if you prefer a fixed IP
- `TAPO_USERNAME`
- `TAPO_PASSWORD`
- `TRIGGER_EVENT_TYPES=7,8`
- `POWER_CUT_START_HOUR=21`
- `POWER_CUT_END_HOUR=9`

If `TAPO_ALIAS` is set, the service will scan the LAN and pick the plug whose alias matches that value case-insensitively. If `TAPO_ALIAS` is blank, it falls back to `TAPO_HOST`.

## Local Commands

Check that the TAPO plug can be reached:

```bash
. .venv/bin/activate
print-ai-monitor probe-plug
```

Toggle the configured TAPO plug:

```bash
. .venv/bin/activate
PYTHONPATH=src python scripts/toggle_tapo_plug.py
```

Start the webhook service:

```bash
. .venv/bin/activate
print-ai-monitor serve
```

## OctoEverywhere Setup

In OctoEverywhere Custom Webhook Setup:

- Enable `Use LAN Webhook Requests`
- Webhook URL:
  - `http://127.0.0.1:8787/webhook/octoeverywhere` if OctoEverywhere runs natively on the same Pi
  - `http://<pi-lan-ip>:8787/webhook/octoeverywhere` if OctoEverywhere runs in a container or cannot reach loopback
- Secret Key: the same value as `OCTOEVERYWHERE_SECRET`

OctoEverywhere can send many notification types. This service only acts on the configured trigger events, which default to `EventType=7` and `EventType=8`, and only during the configured power-cut window, which defaults to `21:00-09:00`.

## systemd

Copy the unit file and adjust paths if your install location differs:

```bash
sudo cp systemd/print-ai-monitor.service /etc/systemd/system/print-ai-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable --now print-ai-monitor.service
sudo systemctl status print-ai-monitor.service
```

## Test

```bash
. .venv/bin/activate
pytest
```

## Manual Verification

1. Run `print-ai-monitor probe-plug` and confirm the expected plug alias is discovered.
2. Start the service and verify `curl http://127.0.0.1:8787/healthz` returns `{"status":"ok"}`.
3. Use OctoEverywhere's webhook test and confirm the service logs an ignored event.
4. Send a local sample trigger:

```bash
curl -X POST http://127.0.0.1:8787/webhook/octoeverywhere \
  -H "content-type: application/json" \
  -d '{
    "EventType": 8,
    "PrintId": "demo-print-id",
    "SecretKey": "replace-me"
  }'
```

The expected response is `{"status":"success","action":"plug_off"}` and the TAPO plug should switch off.
