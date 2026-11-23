# GitHub Issues

## v1 (Stage 1)

### Bootstrap switchboard-room gateway service with Stage 1 endpoints and mocked downstream client
Target: /services/switchboard-room
Summary: Scaffold Python 3.12+ / FastAPI gateway service (switchboard-room) implementing public OpenAPI contract (/api/session, /api/action, /api/traces/{session_id}) and /health, with OTel OTLP/HTTP trace emission (forceFlush before response) and ENV=local / ENV=prod OIDC token handling. Back downstream calls to chime-regulator (/internal/regulate, /internal/traces/{session_id}) with a swappable mock client returning valid Stage 1 responses.
Desired Outcome:
- Runs locally and passes offline pytest + httpx.AsyncClient unit tests for /health, POST /api/session, POST /api/action (Stage 1 PROBE, CALIBRATE, ENGAGE, RESET), and GET /api/traces/{session_id}.
- Strips any gauge.* span attributes before responses leave the gateway.
- Emits and flushes OTel spans synchronously per request, verified with an in-memory span exporter in tests.
- All request/response payloads strictly conform to openapi.yaml.
- Clean downstream client interface isolates mocked chime-regulator calls so real HTTP routing can be enabled in Issue 2.

### Bootstrap chime-regulator service for Stage 1 evaluation and trace indexing, and wire to switchboard-room
Target: /services/chime-regulator, /services/switchboard-room
Summary: Scaffold FastAPI chime-regulator service implementing /internal/regulate, /internal/traces/{session_id}, and /health, with OTel tracing (forceFlush) and redis.asyncio storage keeping up to the last 5 trace waterfalls per session. Implement Stage 1 evaluation logic using mocked clients for escapement-gear (/internal/tick) and pendulum-cache (/internal/state/{session_id}), then update switchboard-room to call chime-regulator over HTTP instead of its local mock.
Desired Outcome:
- Runs locally and passes offline pytest unit tests using fakeredis and an in-memory OTel span exporter.
- POST /internal/regulate evaluates Stage 1 actions against mocked escapement-gear and pendulum-cache responses, indexes the resulting TraceWaterfall in Redis (capped at 5 newest traces per session), and returns updated StageState, GaugeReadings, and latest_trace conforming to openapi.yaml.
- GET /internal/traces/{session_id} retrieves stored session traces newest-first.
- switchboard-room calls chime-regulator via HTTP client (skipping OIDC in ENV=local, attaching Google OIDC ID tokens in ENV=prod), with graceful degradation if trace indexing fails.

### Bootstrap escapement-gear service with Stage 1 cold-start timing engine, and wire to chime-regulator
Target: /services/escapement-gear, /services/chime-regulator
Summary: Scaffold FastAPI escapement-gear service implementing /internal/tick and /health, with OTel tracing (forceFlush) and Stage 1 cold-start detection (container.cold_start = true on initial wake-up, warm baseline latency thereafter). Update chime-regulator to call escapement-gear over HTTP instead of its mock while keeping pendulum-cache mocked.
Desired Outcome:
- Runs locally and passes offline pytest unit tests verifying POST /internal/tick returns InternalTickResponse (conforming to openapi.yaml) with accurate cold_start, duration_ms, and span metadata (container.cold_start).
- Subsequent calls within a warm instance report warm latency and cold_start = false.
- chime-regulator calls escapement-gear over HTTP (respecting ENV=local vs ENV=prod OIDC auth and per-hop timeouts), incorporating the real child span into the assembled Stage 1 TraceWaterfall.

### Bootstrap pendulum-cache service with Redis session state, and wire chime-regulator for end-to-end Stage 1
Target: /services/pendulum-cache, /services/chime-regulator
Summary: Scaffold FastAPI pendulum-cache service implementing GET /internal/state/{session_id}, POST /internal/state/{session_id}, and /health, backed by redis.asyncio with bounded TTLs and OTel tracing (forceFlush). Replace the final mock in chime-regulator with live HTTP calls to pendulum-cache so Stage 1 executes end-to-end across all four services.
Desired Outcome:
- Runs locally and passes offline pytest unit tests using fakeredis for GET (returning 404 when uncached) and POST /internal/state/{session_id} (CachedSessionState conforming to openapi.yaml).
- chime-regulator persists and reads session warmup/completion state through pendulum-cache over HTTP (with ENV=local / ENV=prod OIDC handling), removing all remaining downstream service mocks.
- All four services (switchboard-room -> chime-regulator -> escapement-gear & pendulum-cache) run together locally against Redis to complete Stage 1 (PROBE cold-to-warm transition and ENGAGE stage completion) end-to-end.

### Implement full Stage 1 wake-up mechanics and analog gauge physics in chime-regulator
Target: /services/chime-regulator, /services/pendulum-cache
Summary: Complete Stage 1 (Wake the Tower) rule engine in chime-regulator so PROBE tracks cold-to-warm transitions across all Stage 1 targets in CachedSessionState.warm_targets, ENGAGE verifies all required targets are warm before marking stage_completed = true, and RESET clears session warmup state back to cold baseline. Compute Stage 1 analog gauge readings (mains_tension, resonance_drag, reserve_pressure) reflecting cold-start spikes versus steady warm idle bands, alongside hidden gauge.* span attributes (gauge.mains_tension.raw, gauge.resonance_drag.spike_ms).
Desired Outcome:
- POST /internal/regulate updates warm_targets via pendulum-cache on PROBE and enforces all targets being warm before ENGAGE completes Stage 1.
- GaugeReadings (mains_tension, resonance_drag, reserve_pressure) shift dynamically between cold-start spikes and warm idle readings per Stage 1 specifications.
- Hidden gauge.* attributes are attached to emitted OTel spans while all request/response payloads strictly conform to openapi.yaml, verified by isolated pytest unit tests.

### Add Stage 1 Field Manual content and Chamber View operational logs
Target: /services/chime-regulator
Summary: Populate structured Stage 1 FieldManualContent (stage_title, how_to_play, stage_hints, and real_world_parallel covering title, summary, and completion_takeaway) and diegetic chamber_logs messages returned inside StageState for Stage 1. Ensure copy adheres to industrial-maritime visual guardrails (no exclamation marks, emojis, or narrative fluff).
Desired Outcome:
- StageState.manual and StageState.chamber_logs return complete, structured Stage 1 briefing text, progressive diagnostic hints, and post-completion real-world parallel takeaways.
- All copy follows design guardrails (restrained technical tone, zero exclamation marks or emojis).
- Responses validate cleanly against FieldManualContent and StageState schemas in openapi.yaml in isolated pytest unit tests.

### Integrate Lovable frontend in /apps/web with live switchboard-room gateway API
Target: /apps/web
Summary: Import generated Vite + React + TypeScript frontend into /apps/web and replace mock data layer with live HTTP calls to POST /api/session, POST /api/action, and GET /api/traces/{session_id} against switchboard-room. Verify CRT Chamber View, Trace View waterfall inspector, analog gauges, and Field Manual focus-swap transitions work cleanly against live API payloads conforming to openapi.yaml.
Desired Outcome:
- /apps/web builds cleanly and connects to switchboard-room using openapi.yaml request/response contracts.
- Players can run PROBE, CALIBRATE, ENGAGE, and RESET from the switchboard console, inspect live trace waterfalls in Trace View, and view Stage 1 Field Manual tabs.
- Frontend API client types and runtime responses match openapi.yaml with zero remaining mock fallbacks required for Stage 1 gameplay.


### Add slim multi-stage Dockerfiles and GitHub Actions auto-deploy pipeline
Target: /services/switchboard-room, /services/chime-regulator, /services/escapement-gear, /services/pendulum-cache, /.github/workflows/deploy.yml
Summary: Add ultra-slim multi-stage Dockerfiles (`uv` + `python:3.12-slim` with `--no-install-recommends` and stripped caches, targeting <75 MB per image) for all four services. Create a GitHub Actions workflow triggered on pushes to `main` that builds and pushes images for changed services to the single-region Artifact Registry and updates their Cloud Run revisions via `gcloud run deploy --image`.
Desired Outcome:
- All four services build cleanly into slim container images under 75 MB each (~250 MB total across all 4 services).
- Merging to `main` automatically builds and pushes updated service images to Artifact Registry and rolls out new Cloud Run revisions.
- Workflow authenticates via Google Cloud Workload Identity Federation using repository secrets/variables.

## v2 (Stages 2-5)

### Support advance_stage session transitions across switchboard-room, chime-regulator, and pendulum-cache
Target: /services/switchboard-room, /services/chime-regulator, /services/pendulum-cache
Summary: Implement handling for the optional advance_stage boolean in POST /api/session as defined in openapi.yaml (do not modify openapi.yaml). When advance_stage is true and the active session has stage_completed = true (with stage_id < 5), increment stage_id to stage_id + 1, reset stage-specific flags (stage_completed = false, warm_targets, calibrated_targets, calibration_values) in pendulum-cache, and return the fresh SessionResponse for the new stage. Ignore advance_stage if the current stage is not completed or already at stage 5.
Desired Outcome:
- POST /api/session with { session_id, advance_stage: true } advances a completed stage N to stage N + 1 and resets stage-scoped cached state.
- Calling POST /api/session with advance_stage: true when stage_completed is false or stage_id is 5 safely returns the current session without incrementing.
- All payloads conform strictly to openapi.yaml (without modifying openapi.yaml), verified by isolated pytest unit tests.

### Implement Stage 2 synthetic resonance latency engine in escapement-gear
Target: /services/escapement-gear
Summary: Update POST /internal/tick in escapement-gear to support Stage 2 (Resonance Tuning) by introducing a synthetic asyncio.sleep delay proportional to the delta between the calibrated slider value (0-100, step 5) and a hidden target resonant frequency. Emit escapement.detune_delta and hidden gauge.resonance_drag.oscillation_hz span attributes.
Desired Outcome:
- POST /internal/tick introduces deterministic latency proportional to detune distance in Stage 2, dropping below 200ms when tuned to the resonant notch.
- Emits escapement.detune_delta and gauge.resonance_drag.oscillation_hz attributes on the escapement-gear span.
- Request and response payloads strictly conform to openapi.yaml, verified by isolated pytest unit tests.

### Implement Stage 2 evaluation, gauge physics, and Field Manual content in chime-regulator
Target: /services/chime-regulator
Summary: Add Stage 2 (Resonance Tuning) rules to POST /internal/regulate in chime-regulator so CALIBRATE persists slider values via pendulum-cache, ENGAGE succeeds once escapement-gear span duration drops below 200ms, and gauges reflect resonance drag oscillation versus slider tension. Populate Stage 2 FieldManualContent and chamber_logs following visual guardrails.
Desired Outcome:
- ENGAGE marks Stage 2 complete only when escapement-gear latency is under 200ms and advances session progression.
- GaugeReadings reflect slider notch position on mains_tension and detune oscillation on resonance_drag.
- Stage 2 FieldManualContent and chamber_logs follow design guardrails (zero exclamation marks or emojis) and validate against openapi.yaml in isolated pytest unit tests.

### Add staggered TTL cache keys and telemetry metadata to pendulum-cache for Stage 3
Target: /services/pendulum-cache
Summary: Extend pendulum-cache to support Stage 3 (Cache Warmth and TTL Decay) per-target pneumatic reserve keys in Redis with staggered TTLs (30s, 20s, and 15s for the three targets). Return cache hit status and remaining TTL metadata so spans can record cache.hit, cache.ttl_remaining_ms, and hidden cache.expires_at_epoch_ms attributes.
Desired Outcome:
- Writing a target calibration in Stage 3 sets its Redis key with the target-specific staggered TTL (30s, 20s, or 15s) and reports cache.hit = true alongside remaining TTL.
- Expired keys cleanly report cache.hit = false without crashing or returning stale state.
- Isolated pytest unit tests using fakeredis verify TTL expiration behavior and openapi.yaml schema conformance.

### Implement Stage 3 multi-target TTL validation, decay gauges, and Field Manual in chime-regulator
Target: /services/chime-regulator
Summary: Add Stage 3 (Cache Warmth and TTL Decay) evaluation to chime-regulator so ENGAGE verifies all three target keys are simultaneously warm in pendulum-cache before completing the stage. Compute reserve_pressure decay proportional to remaining TTLs, emit cache.* and hidden gauge.reserve_pressure.psi span attributes, and add Stage 3 FieldManualContent and chamber_logs.
Desired Outcome:
- ENGAGE succeeds in Stage 3 only if all three staggered-TTL keys are active simultaneously; any expired key triggers a cache-miss failure state.
- GaugeReadings dynamically reflect combined reserve_pressure charge and real-time TTL decay, plus drag spikes on cache misses.
- Stage 3 manual and logs adhere to visual guardrails and pass openapi.yaml schema validation in isolated pytest unit tests.

### Emit counterweight nominal and delta span attributes in escapement-gear for Stage 4
Target: /services/escapement-gear
Summary: Update POST /internal/tick in escapement-gear to support Stage 4 (Hidden Span Attributes) by evaluating each subsystem's hidden target counterweight (gear.nominal_load) against its current calibrated value (gear.current_load) and emitting gear.nominal_load, gear.current_load, and gear.delta as structured span attributes without exposing target values in chamber logs.
Desired Outcome:
- Child spans emitted during Stage 4 PROBE and CALIBRATE include accurate gear.nominal_load, gear.current_load, and gear.delta attributes.
- Hidden target values remain omitted from user-facing message strings while conforming to openapi.yaml Span schema.
- Verified with isolated pytest unit tests and an in-memory OTel span exporter.

### Implement Stage 4 counterweight validation, deflection gauges, and Field Manual in chime-regulator
Target: /services/chime-regulator
Summary: Add Stage 4 (Hidden Span Attributes) rule evaluation to chime-regulator so ENGAGE succeeds only when gear.delta equals 0 across all three subsystems. Compute mains_tension proportional to the active target's gear.nominal_load and resonance_drag vibration proportional to total gear.delta, emit hidden gauge.* attributes, and add Stage 4 FieldManualContent and chamber_logs.
Desired Outcome:
- ENGAGE completes Stage 4 only when all three targets match their hidden nominal loads (gear.delta == 0).
- GaugeReadings deflect mains_tension by selected nominal load and vibrate resonance_drag by total imbalance while emitting hidden gauge.mains_tension.deflection_deg and gauge.resonance_drag.jitter_index attributes.
- Stage 4 manual and logs follow design guardrails and validate against openapi.yaml in isolated pytest unit tests.

### Persist and vent circuit-breaker fault state in pendulum-cache for Stage 5
Target: /services/pendulum-cache
Summary: Extend CachedSessionState persistence in pendulum-cache to store and clear the Stage 5 safety pawl circuit-breaker tripped flag in Redis so breaker state survives across stateless Cloud Run instances and vents cleanly when RESET is triggered.
Desired Outcome:
- pendulum-cache persists and returns circuit-breaker state per session in Redis with bounded TTLs.
- Resetting session state clears the tripped breaker flag back to closed baseline.
- Verified via isolated pytest unit tests with fakeredis and strict conformance to openapi.yaml.

### Implement Stage 5 torque budget, circuit breaker, and Field Manual in chime-regulator
Target: /services/chime-regulator
Summary: Add Stage 5 (Cascading Backpressure and Circuit Breakers) evaluation to chime-regulator requiring combined subsystem torque between 120 and 150 inclusive. Exceeding 150 during CALIBRATE or ENGAGE trips the safety pawl circuit breaker (span.status = ERROR, breaker.tripped span event, breaker.state = TRIPPED, gauge.mains_tension.overload_pct > 100), rejecting downstream calls until RESET vents the fault in pendulum-cache. Add Stage 5 gauge behavior, FieldManualContent, and chamber_logs.
Desired Outcome:
- Combined torque above 150 trips and persists the circuit breaker, marking span status ERROR, recording a breaker.tripped event, pinning mains_tension, and blocking ENGAGE until RESET is executed.
- Combined torque within 120-150 while the breaker is closed allows ENGAGE to complete Stage 5.
- Stage 5 manual and logs follow design guardrails and pass openapi.yaml validation in isolated pytest unit tests.

### Add CI-only cloud-backed end-to-end integration test suite
Target: /tests/e2e, /.github/workflows/deploy.yml
Summary: Create an end-to-end integration test suite (`pytest`) gated strictly behind `CI=true` (skipping automatically when run locally) that exercises the live deployed Cloud Run topology through `https://clocktower.littlefuzzydinos.com/api/*`. Verify session creation, `advance_stage` transitions, Stages 1 through 5 completion criteria, Redis state persistence across requests, trace waterfall structure, and stripping of all `gauge.*` span attributes. Run this suite automatically in GitHub Actions after Cloud Run deployments complete.
Desired Outcome:
- Running `pytest` locally skips the E2E suite unless `CI=true` and `E2E_BASE_URL` are explicitly set.
- In GitHub Actions post-deploy, the suite verifies end-to-end gameplay across Stages 1–5 against the live Cloud Run services and Upstash Redis.
- Tests assert strict conformance to `openapi.yaml` and confirm zero `gauge.*` keys leak into `/api/action` or `/api/traces/{session_id}` responses.
