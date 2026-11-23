# System Architecture — The Clock Tower

## 1. System Overview & Design Principles

*The Clock Tower* is an interactive distributed-systems observability puzzle designed around four core architectural principles:

* **Strict Service Isolation:** Each backend service (`switchboard-room`, `chime-regulator`, `escapement-gear`, `pendulum-cache`) lives in its own directory with an independent `pyproject.toml`, `uv.lock`, and slim container image. Services never import code across directory boundaries and communicate exclusively over HTTP using contracts defined in `openapi.yaml`.
* **Contract-First Development (`openapi.yaml`):** `openapi.yaml` is the single source of truth for both public gateway endpoints (`/api/*`) and internal downstream endpoints (`/internal/*`), enabling parallel frontend development (via mock adapters) and isolated per-service unit testing.
* **Dual-Path Observability:** Every player action generates structured OpenTelemetry spans across the call chain while simultaneously assembling a deterministic trace waterfall returned to the browser UI so players solve mechanical failures by reading traces rather than text logs.
* **Zero-Cost Cloud Footprint:** All services run as stateless, scale-to-zero Cloud Run containers in a single GCP region backed by serverless Redis, keeping compute, image storage, and intra-region network egress within free-tier limits.

---

## 2. Component Architecture & Service Responsibilities

```text
+-------------------------------------------------------------------+
|                        Browser Client (app/web)                   |
|                 Vite + React + TypeScript (Cloudflare)            |
+---------------------------------+---------------------------------+
                                  | HTTPS (/api/*)
                                  v
+-------------------------------------------------------------------+
|                   switchboard-room (Public Gateway)               |
|  - Exposes /api/session, /api/action, /api/traces/{session_id}    |
|  - Strips gauge.* span attributes before returning traces to UI   |
|  - Flushes OpenTelemetry spans before sending HTTP responses      |
+---------------------------------+---------------------------------+
                                  | Cloud Run IAM Authenticated
                                  | (/internal/session, /internal/regulate, /internal/traces)
                                  v
+-------------------------------------------------------------------+
|               chime-regulator (Rule Engine & Assembler)           |
|  - Evaluates Stage 1–5 puzzle rules & analog gauge physics        |
|  - Orchestrates calls to escapement-gear & pendulum-cache         |
|  - Assembles TraceWaterfall & maintains 5-trace session buffer    |
+----------------+---------------------------------+----------------+
                 | /internal/tick                  | /internal/state/{id}
                 v                                 v
+---------------------------------+ +-------------------------------+
|        escapement-gear          | |        pendulum-cache         |
|  - Simulates cold starts,       | |  - Wraps Redis session state  |
|    resonance latency, &         | |  - Manages staggered TTL keys |
|    counterweight span deltas    | |  - Persists circuit breaker   |
+---------------------------------+ +---------------+---------------+
                                                    | TLS (REDIS_URL)
                                                    v
                                    +-------------------------------+
                                    |         Upstash Redis         |
                                    |  (Bounded TTL Session State)  |
                                    +-------------------------------+
```

### Service Breakdown

| Component | Visibility | Responsibility |
| :--- | :--- | :--- |
| **`app/web`** | Public (Cloudflare Pages) | Renders the bolted-steel switchboard console, three analog chamber gauges, Engineer's Field Manual, and interactive distributed trace waterfall viewer. |
| **`switchboard-room`** | Public (`allUsers` invoker) | Public API gateway. Exposes `/health` and `/api/*`, forwards requests to `chime-regulator` with OIDC tokens when `ENV=prod` or runs standalone when `CHIME_REGULATOR_MODE=mock`, strips `gauge.*` attributes before browser delivery, and flushes OTel spans. |
| **`chime-regulator`** | Internal (IAM-restricted) | Core puzzle orchestrator. Computes `StageState` and `GaugeReadings`, coordinates downstream calls, assembles `TraceWaterfall` payloads, and maintains the rolling 5-trace history per session. |
| **`escapement-gear`** | Internal (IAM-restricted) | Mechanical timing simulator. Models cold-start penalties (Stage 1), detuned resonance latency (Stage 2), and hidden counterweight load attributes (Stage 4). |
| **`pendulum-cache`** | Internal (IAM-restricted) | Persistence boundary over Redis. Stores `CachedSessionState`, staggered per-target TTL keys (Stage 3), and circuit-breaker fault flags (Stage 5). |

---

## 3. Request Lifecycle & Sequence Flow

### Session Initialization & Stage Progression (`POST /api/session`)

1. `app/web` calls `POST /api/session` on startup (with `session_id: null` or a stored `session_id`) or when the player clicks **NEXT STAGE** inside the Field Manual (`{ session_id, advance_stage: true }`).
2. `switchboard-room` forwards the session request to `chime-regulator` (`POST /internal/session`).
3. `chime-regulator` queries `pendulum-cache` (`GET /internal/state/{session_id}`):
   * If no session exists, a fresh session is initialized at `stage_id = 1` and persisted via `POST /internal/state/{session_id}`.
   * If `advance_stage: true` and `stage_completed == true` (with `stage_id < 5`), `stage_id` increments to `N + 1`, stage-specific flags (`stage_completed`, `warm_targets`, `calibrated_targets`, `calibration_values`) reset, and the updated state is saved.
4. `switchboard-room` returns the `SessionResponse` containing `state`, `gauges`, and `recent_traces` (with `gauge.*` attributes stripped).

### Control Action Execution (`POST /api/action`)

```text
Browser          switchboard-room      chime-regulator      pendulum-cache      escapement-gear
  |                     |                     |                   |                    |
  |-- POST /api/action >|                     |                   |                    |
  |                     |-- /internal/regulate>|                  |                    |
  |                     |                     |-- GET /state ---->|                    |
  |                     |                     |<-- CachedState ---|                    |
  |                     |                     |                   |                    |
  |                     |                     |-- POST /internal/tick ---------------->|
  |                     |                     |<-- InternalTickResponse (span) --------|
  |                     |                     |                   |                    |
  |                     |                     |-- POST /state --->|                    |
  |                     |                     |<-- SavedState ----|                    |
  |                     |<-- ActionResponse --|                   |                    |
  |                     | (strip gauge.*)     |                   |                    |
  |                     | (flush OTel spans)  |                   |                    |
  |<-- 200 OK ----------|                     |                   |                    |
```

1. **Ingress (`switchboard-room`):** Receives `{ session_id, stage_id, action, target, value }` (`PROBE`, `CALIBRATE`, `ENGAGE`, or `RESET`) and invokes `POST /internal/regulate` on `chime-regulator`.
2. **State Lookup (`chime-regulator` -> `pendulum-cache`):** Fetches current session warmup, calibration values, TTL metadata, and circuit-breaker state.
3. **Mechanical Simulation (`chime-regulator` -> `escapement-gear`):** Invokes `POST /internal/tick` to compute stage-specific timing, synthetic latency, and diagnostic span attributes.
4. **Rule Evaluation & Persistence:** `chime-regulator` evaluates win/fault conditions, updates analog gauge needles (`mains_tension`, `resonance_drag`, `reserve_pressure`), persists the new state in `pendulum-cache`, and records the assembled `TraceWaterfall` in the session's rolling 5-trace buffer.
5. **Sanitization & Flush (`switchboard-room`):** Strips all `gauge.*` keys from every span's `attributes` dictionary before returning `ActionResponse` to the browser, and explicitly flushes the OpenTelemetry `TracerProvider` so Cloud Run does not drop spans after freezing CPU post-response.

---

## 4. Data & State Management

* **Bounded Redis Persistence (`pendulum-cache`):**
  * Primary session document stored under `clocktower:session:{session_id}` with a bounded sliding TTL so abandoned sessions expire automatically without manual cleanup.
  * Stage 3 staggered pneumatic reserve keys stored under `clocktower:reserve:{session_id}:{target}` with target-specific Redis TTLs (`30s`, `20s`, `15s`) so cache expiration is driven natively by Redis key expiry.
* **Rolling Trace Buffer (`chime-regulator`):**
  * Stores up to `TRACE_HISTORY_LIMIT` (default `5`) most recent `TraceWaterfall` objects per `session_id` (newest first) in Redis under `clocktower:traces:{session_id}` with `TRACE_TTL_SECONDS` (default `3600s`) via `REDIS_URL`, degrading gracefully if Redis is unavailable, to power `GET /api/traces/{session_id}`.
* **Stateless Cloud Run Compatibility:**
  * No gameplay state required across requests is pinned solely to local process memory; circuit-breaker trips (Stage 5) and target warmups persist in Redis so requests routed across distinct Cloud Run instances behave deterministically.

---

## 5. Observability & Telemetry Pipeline

1. **In-Game Waterfall Assembly:**
   * Each backend operation produces a structured `Span` (`span_id`, `parent_span_id`, `service_name`, `operation_name`, `start_offset_ms`, `duration_ms`, `status`, `attributes`) combined into a `TraceWaterfall` returned directly in `ActionResponse`.
2. **Attribute Filtering Boundary:**
   * Internal spans carry both player-facing diagnostic attributes (e.g., `cold_start`, `escapement.detune_delta`, `cache.ttl_remaining_ms`, `gear.delta`, `breaker.state`) and telemetry-only `gauge.*` attributes (e.g., `gauge.mains_tension.overload_pct`).
   * `switchboard-room` acts as the egress filter, removing all keys prefixed with `gauge.` before serializing responses to the frontend.
3. **External OTLP Export (v3 Honeycomb Roadmap):**
   * All four services initialize OpenTelemetry tracing using W3C `traceparent` context propagation across HTTP boundaries.
   * When `OTEL_EXPORTER_OTLP_ENDPOINT` or `HONEYCOMB_API_KEY` is present in the environment, spans export via OTLP/HTTP with full `gauge.*` attributes intact, defaulting the endpoint to Honeycomb when only `HONEYCOMB_API_KEY` is set; when unset, tracing fails open with zero impact on gameplay latency.

---

## 6. Deployment & Security Boundary (GCP & Cloudflare)

* **Edge Routing (`Cloudflare`):**
  * `clocktower.littlefuzzydinos.com` serves the static Vite bundle from Cloudflare Pages and routes `/api/*` requests directly to the public `switchboard-room` Cloud Run URL.
* **Compute Isolation (`Google Cloud Run`):**
  * All four services run in a single GCP region with `min_instances = 0` (scale-to-zero) and minimal CPU/memory allocations.
  * Only `switchboard-room` allows unauthenticated public ingress (`allUsers`). `chime-regulator`, `escapement-gear`, and `pendulum-cache` enforce IAM authentication (`roles/run.invoker` granted exclusively to calling service accounts) and internal/cloud-only ingress.
* **Container Registry & CI/CD (`Artifact Registry` + `GitHub Actions`):**
  * Multi-stage `uv` + `python:3.15-slim` builds keep each service image under ~75 MB (~250 MB total across all four services).
  * A single-region Artifact Registry repository with a cleanup policy retaining only the latest 2 image tags per service keeps storage under the 500 MB free tier and ensures intra-region image pulls incur $0 egress.
  * GitHub Actions authenticates via Workload Identity Federation (OIDC), builds/pushes changed services on pushes to `main`, rolls out new Cloud Run revisions, and executes the `CI=true` end-to-end integration test suite against the live deployment.
