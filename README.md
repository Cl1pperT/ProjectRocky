# Print AI Monitor

`print-ai-monitor` runs on a Raspberry Pi and listens for OctoEverywhere webhook events. When OctoEverywhere reports `EventType=8` (`Gadget Paused Print Due To Failure`), the service turns off a TAPO P125M smart plug over the local network.

## What It Does

- Exposes `POST /webhook/octoeverywhere` for OctoEverywhere LAN webhooks.
- Exposes `GET /healthz` for liveness checks.
- Authenticates webhook payloads with a shared secret.
- Ignores all events except `EventType=8`.
- Suppresses duplicate shutdown attempts for the same `PrintId`.
- Retries local TAPO power-off requests on transient failures.

## Requirements

- Raspberry Pi Zero 2 W or better
- Python 3.11+
- OctoEverywhere already installed
- TAPO P125M already paired to your LAN and reachable by IP
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
- `TAPO_HOST`
- `TAPO_USERNAME`
- `TAPO_PASSWORD`

## Local Commands

Check that the TAPO plug can be reached:

```bash
. .venv/bin/activate
print-ai-monitor probe-plug
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

OctoEverywhere can send many notification types. This service only acts on `EventType=8` and will acknowledge the rest without shutting off power.

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

1. Run `print-ai-monitor probe-plug` and confirm the plug is discovered.
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
