# The Clock Tower

**Live Application:** [https://clocktower.littlefuzzydinos.com](https://clocktower.littlefuzzydinos.com)

*The Clock Tower* is an interactive distributed-systems observability puzzle game. Players act as clockwork engineers stabilizing a multi-service mechanical tower across five escalating stages—diagnosing cold starts, resonance latency, cache TTL decay, hidden span attributes, and cascading circuit-breaker faults by reading live distributed trace waterfalls and analog chamber gauges rather than traditional text logs.

## Screenshots

| Switchboard Console & Analog Gauges | Distributed Trace Waterfall & Field Manual |
| :---: | :---: |
| ![Switchboard Console](docs/images/switchboard-console.png) | ![Trace Waterfall](docs/images/trace-waterfall.png) |

## Architecture Overview

The application is built as a strictly decoupled four-service backend behind a single-page React console:

```text
app/web (React / Vite)
   │  POST /api/session, POST /api/action, GET /api/traces/{session_id}
   ▼
switchboard-room (Public Gateway — strips gauge.* attributes & flushes OTel spans)
   │  POST /internal/regulate, GET /internal/traces/{session_id}
   ▼
chime-regulator (Rule Engine & Trace Waterfall Assembler)
   ├──► escapement-gear (Mechanical timing, cold-start, & latency simulator)
   └──► pendulum-cache (Redis-backed session state & staggered TTL store)
```

For full request sequence diagrams, stage physics, and infrastructure details, see [`docs/architecture.md`](docs/architecture.md) and [`docs/plan.md`](docs/plan.md).

---

## Local Development

### Tech Stack & Prerequisites

* **Backend Services:** Python 3.15, [`uv`](https://docs.astral.sh/uv/) 0.13, FastAPI, OpenTelemetry SDK
* **State Store:** Redis (local instance or Docker container for `pendulum-cache`)
* **Frontend (`app/web`):** Node.js 22+, Vite, React, TypeScript
* **API Contract:** OpenAPI 3.1 (`openapi.yaml` as the single source of truth)

### Running the Services

Each microservice manages its own isolated virtual environment and dependencies via `uv`. Open separate terminals for Redis and each service:

1. **Start Local Redis**
   ```bash
   docker run --rm -p 6379:6379 redis:7-alpine
   ```

2. **Start `pendulum-cache` (Port 8004)**
   ```bash
   cd services/pendulum-cache
   REDIS_URL="redis://localhost:6379/0" uv run uvicorn pendulum_cache.main:app --port 8004 --reload
   ```

3. **Start `escapement-gear` (Port 8003)**
   ```bash
   cd services/escapement-gear
   uv run uvicorn escapement_gear.main:app --port 8003 --reload
   ```

4. **Start `chime-regulator` (Port 8002)**
   ```bash
   cd services/chime-regulator
   ESCAPEMENT_GEAR_URL="http://localhost:8003" \
   PENDULUM_CACHE_URL="http://localhost:8004" \
   uv run uvicorn chime_regulator.main:app --port 8002 --reload
   ```

5. **Start `switchboard-room` (Port 8001)**
   ```bash
   cd services/switchboard-room
   CHIME_REGULATOR_URL="http://localhost:8002" \
   uv run uvicorn switchboard_room.main:app --port 8001 --reload
   ```

6. **Start the Frontend (`app/web`)**
   ```bash
   cd app/web
   npm install
   VITE_API_BASE_URL="http://localhost:8001" npm run dev
   ```
   *(To run the frontend standalone without backend services, omit `VITE_API_BASE_URL` to use the built-in mock adapter.)*

### Running Tests

* **Isolated Service Unit Tests:** Run `pytest` inside any individual service directory (`fakeredis` and in-memory OpenTelemetry exporters are used so no external network or Redis instance is required):
  ```bash
  cd services/chime-regulator
  uv run pytest
  ```
* **Cloud End-to-End Integration Tests:** The suite under `tests/e2e` targets the live Cloud Run deployment and is strictly gated behind `CI=true` so it skips automatically during local test runs.

---

## Repository Structure

```text
clocktower/
├── AGENTS.md                  # Guardrails for AI coding agents (service isolation, contract rules)
├── README.md                  # Portfolio overview, local development, and roadmap
├── openapi.yaml               # Single source of truth for public & internal REST schemas
├── docs/
│   ├── architecture.md        # System design, sequence flows, and deployment topology
│   ├── plan.md                # Stage 1–5 puzzle mechanics, gauge physics, and design rules
│   └── images/                # Screenshots referenced in README.md
├── .github/
│   └── workflows/
│       └── deploy.yaml        # Path-filtered Artifact Registry builds, Cloud Run deploy, & E2E tests
├── app/
│   └── web/                   # Vite + React + TypeScript switchboard UI
├── services/
│   ├── switchboard-room/      # Public gateway, OTel trace flushing, & gauge.* attribute stripping
│   │   ├── README.md
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   └── tests/
│   ├── chime-regulator/       # Stage evaluation engine & trace waterfall assembler
│   │   ├── README.md
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   └── tests/
│   ├── escapement-gear/       # Mechanical timing, cold-start, & synthetic latency simulator
│   │   ├── README.md
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   └── tests/
│   └── pendulum-cache/        # Redis session & staggered TTL persistence service
│       ├── README.md
│       ├── Dockerfile
│       ├── pyproject.toml
│       ├── src/
│       └── tests/
└── tests/
    └── e2e/                   # CI-only end-to-end integration tests against live Cloud Run
```

---

## Roadmap: v3 Honeycomb Integration

Following completion of the core five-stage puzzle loop and automated Cloud Run pipeline, the v3 observability expansion will add live external telemetry export:

* **Direct-to-Honeycomb OTLP Export:** Configure OpenTelemetry OTLP/HTTP exporters across `switchboard-room`, `chime-regulator`, `escapement-gear`, and `pendulum-cache` gated by `HONEYCOMB_API_KEY` (continuing to fail open gracefully when unset).
* **Rich `gauge.*` Telemetry Attributes:** Emit stage-specific physical telemetry on backend spans (`gauge.mains_tension.*`, `gauge.resonance_drag.*`, `gauge.reserve_pressure.*`) for live Honeycomb query boards while stripping `gauge.*` keys in `switchboard-room` before traces reach the browser UI.
* **Custom Query Boards & Triggers:** Provide companion Honeycomb board definitions showcasing cold-start latency distributions, cache TTL decay curves, and circuit-breaker error spikes.
