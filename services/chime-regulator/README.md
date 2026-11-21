# chime-regulator

**Role:** Stage Rule Engine & Trace Assembler (`Internal IAM-Restricted` | Local Port: `8002`)

`chime-regulator` is the central puzzle orchestrator for *The Clock Tower*. It evaluates Stage 1–5 win and fault conditions, calculates analog chamber gauge readings (`mains_tension`, `resonance_drag`, `reserve_pressure`), coordinates calls to `escapement-gear` and `pendulum-cache`, and maintains each session's rolling 5-trace waterfall buffer.

## Endpoints

All request and response schemas conform strictly to [`../../openapi.yaml`](../../openapi.yaml).

| Method | Path | Operation ID | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/internal/regulate` | `regulateStageAction` | Evaluate stage mechanics across downstream services and assemble a `TraceWaterfall`. |
| `GET` | `/internal/traces/{session_id}` | `getInternalTraces` | Retrieve stored trace waterfalls (newest first) for a given session. |

## Configuration

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `ESCAPEMENT_GEAR_URL` | Yes | — | Base URL of the `escapement-gear` service (e.g., `http://localhost:8003`). |
| `PENDULUM_CACHE_URL` | Yes | — | Base URL of the `pendulum-cache` service (e.g., `http://localhost:8004`). |
| `PORT` | No | `8002` | HTTP port bound by Uvicorn. |
| `OTEL_SERVICE_NAME` | No | `chime-regulator` | Service name attached to emitted OpenTelemetry spans. |
| `HONEYCOMB_API_KEY` | No | — | Optional API key enabling direct OTLP trace export to Honeycomb (fails open when unset). |

## Local Run & Testing

**Start the service:**
```bash
ESCAPEMENT_GEAR_URL="http://localhost:8003" \
PENDULUM_CACHE_URL="http://localhost:8004" \
uv run uvicorn chime_regulator.main:app --port 8002 --reload
```

**Run isolated unit tests:**
```bash
uv run pytest
```
