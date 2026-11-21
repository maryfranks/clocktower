# pendulum-cache

**Role:** Redis Session & TTL State Service (`Internal IAM-Restricted` | Local Port: `8004`)

`pendulum-cache` isolates all Redis persistence for *The Clock Tower*. It stores bounded-TTL session progression state (`CachedSessionState`), manages staggered per-target pneumatic reserve TTL keys (`30s`, `20s`, `15s` in Stage 3), and persists safety-pawl circuit-breaker fault flags across stateless Cloud Run instances (Stage 5).

## Endpoints

All request and response schemas conform strictly to [`../../openapi.yaml`](../../openapi.yaml).

| Method | Path | Operation ID | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/internal/state/{session_id}` | `getCachedSessionState` | Read cached session warmup, calibration, and stage completion state from Redis. |
| `POST` | `/internal/state/{session_id}` | `setCachedSessionState` | Persist updated session state in Redis with a bounded TTL. |

## Configuration

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `REDIS_URL` | Yes | — | Redis connection URI (e.g., `redis://localhost:6379/0` or Upstash TLS URI). |
| `PORT` | No | `8004` | HTTP port bound by Uvicorn. |
| `OTEL_SERVICE_NAME` | No | `pendulum-cache` | Service name attached to emitted OpenTelemetry spans. |
| `HONEYCOMB_API_KEY` | No | — | Optional API key enabling direct OTLP trace export to Honeycomb (fails open when unset). |

## Local Run & Testing

**Start the service:**
```bash
REDIS_URL="redis://localhost:6379/0" \
uv run uvicorn pendulum_cache.main:app --port 8004 --reload
```

**Run isolated unit tests (uses `fakeredis`):**
```bash
uv run pytest
```
