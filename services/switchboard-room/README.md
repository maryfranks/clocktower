# switchboard-room

**Role:** Public API Gateway (`Public Ingress` | Local Port: `8001`)

`switchboard-room` is the public-facing FastAPI gateway for *The Clock Tower*. It validates incoming browser requests from `app/web`, forwards gameplay commands to `chime-regulator`, strips internal `gauge.*` span attributes before returning trace waterfalls to the client, and flushes OpenTelemetry spans prior to completing responses.

## Endpoints

All request and response schemas conform strictly to [`../../openapi.yaml`](../../openapi.yaml).

| Method | Path | Operation ID | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/session` | `createOrResumeSession` | Create a new session, resume an existing session, or advance to the next stage (`advance_stage: true`). |
| `POST` | `/api/action` | `executeControlAction` | Execute a physical switchboard control action (`PROBE`, `CALIBRATE`, `ENGAGE`, `RESET`). |
| `GET` | `/api/traces/{session_id}` | `getSessionTraces` | Retrieve up to the 5 most recent sanitized trace waterfalls for a session. |

## Configuration

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `CHIME_REGULATOR_URL` | Yes | — | Base URL of the `chime-regulator` service (e.g., `http://localhost:8002`). |
| `PORT` | No | `8001` | HTTP port bound by Uvicorn. |
| `OTEL_SERVICE_NAME` | No | `switchboard-room` | Service name attached to emitted OpenTelemetry spans. |
| `HONEYCOMB_API_KEY` | No | — | Optional API key enabling direct OTLP trace export to Honeycomb (fails open when unset). |

## Local Run & Testing

**Start the service:**
```bash
CHIME_REGULATOR_URL="http://localhost:8002" \
uv run uvicorn switchboard_room.main:app --port 8001 --reload
```

**Run isolated unit tests:**
```bash
uv run pytest
```

### Docker Build

To build the image, run
```bash
docker build -f services/switchboard-room/deploy/Dockerfile services/switchboard-room
```
from the root of the repo.
