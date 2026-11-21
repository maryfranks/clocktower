# escapement-gear

**Role:** Mechanical Timing & Latency Simulator (`Internal IAM-Restricted` | Local Port: `8003`)

`escapement-gear` simulates the physical timing behavior of the clockwork tower across stages. It models cold-start initialization penalties (Stage 1), detuned resonance latency delays (Stage 2), and hidden counterweight load attributes (`gear.nominal_load`, `gear.current_load`, `gear.delta` in Stage 4), returning structured child spans to `chime-regulator`.

## Endpoints

All request and response schemas conform strictly to [`../../openapi.yaml`](../../openapi.yaml).

| Method | Path | Operation ID | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/internal/tick` | `tickEscapementGear` | Simulate mechanical escapement timing, synthetic latency, and diagnostic span attributes. |

## Configuration

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | No | `8003` | HTTP port bound by Uvicorn. |
| `OTEL_SERVICE_NAME` | No | `escapement-gear` | Service name attached to emitted OpenTelemetry spans. |
| `HONEYCOMB_API_KEY` | No | — | Optional API key enabling direct OTLP trace export to Honeycomb (fails open when unset). |

## Local Run & Testing

**Start the service:**
```bash
uv run uvicorn escapement_gear.main:app --port 8003 --reload
```

**Run isolated unit tests:**
```bash
uv run pytest
```
