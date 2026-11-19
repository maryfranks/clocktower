# The Clock Tower — Master Architecture & Design Blueprint

**The Clock Tower** is a browser-based distributed systems diagnostic puzzle game set inside a stalled monumental clock tower. Operating an early 20th-century brass-and-steel relay switchboard, players troubleshoot and bring four coupled clockwork subsystems back online across five escalating stages—using real OpenTelemetry distributed traces, span durations, attributes, and error states emitted by live microservices as their primary diagnostic instruments.

---

## Overview & Theme

* **Goal & Aesthetic:** Players operate an early 20th-century naval relay switchboard to troubleshoot and restore power to a stalled monumental clock tower. Rather than relying on heavy text exposition, the game treats real OpenTelemetry traces, latency shifts, span attributes, and error states from live clockwork microservices as the player's primary diagnostic instruments.
* **The Five Ascending Stages:** Progression moves upward through five self-contained diagnostic puzzles—starting with waking dormant clockwork mechanisms (Stage 1), tuning pendulum resonance latency (Stage 2), managing Redis cache warmth and TTL decay (Stage 3), uncovering hidden sensor tolerances in span attributes (Stage 4), and balancing coupled torque budgets against safety circuit breakers (Stage 5).
* **Phased Rollout:**
  * **v1:** Core switchboard UI, all four backend microservices, and **Stage 1** playable end-to-end using pure OpenTelemetry.
  * **v2:** Incremental rollout of **Stages 2–5** across the existing console interface and microservice contracts.
  * **v3:** Local execution mode allowing players to connect their own Honeycomb accounts and play an expanded version of the game (detailed in the stage specifications below).

---

## Design Direction

* **Overall Theme:** Tactile industrial-maritime switchboard meets classic terminal instrumentation—evoking an early 20th-century master-clock control console built from heavy bolted steel, aged wood, and burnished brass hardware.
* **General Visual Guardrails:**
  * Dark, low-glare interface built around physical hardware metaphors—engraved label plates, mechanical switches, notched sliders, and a recessed monochrome CRT readout screen.
  * Crisp, angular hardware geometry with tight corner radii and structured hairline borders rather than modern rounded SaaS cards or pill buttons.
  * Status indicators rely on mechanical glyphs, borders, and clear text labels rather than color alone, keeping the overall palette restrained and low-glare.
  * Worn, Illegible Gauges: Physical and on-screen console gauges are permanently weathered, corroded, and illegible, forcing players to rely on the telemetry and trace inspector rather than surface dials to diagnose the clockwork.
* **Don'ts:**
  * Avoid exclamation marks, emojis, arcade flashiness, neon glow effects, startup hype copy, or overly dramatic narrative fluff.

---

## System Architecture & Repo Layout

### Architectural Principles & Constraints
* **Zero-Cost Free-Tier Footprint:** Every infrastructure component is engineered to operate comfortably within cloud free-tier quotas—using static edge hosting (Cloudflare Pages), scale-to-zero serverless containers (Cloud Run), and serverless key-value storage (Upstash Redis) with bounded TTLs so memory and request budgets never overrun.
* **Stateless Services & Externalized State:** All four backend services are stateless and scale horizontally from zero. Session state, puzzle calibration values, circuit-breaker flags, and short-TTL trace snapshots live exclusively in Upstash Redis via async, non-blocking clients (`redis.asyncio`), preventing in-memory state drift across cold starts or instance replacements.
* **Independent Deployments & Additive Contracts:** Services communicate over versioned, additive HTTP/JSON contracts (`/v1/...`) where consumers ignore unknown fields and apply safe defaults. Any service can be deployed or rolled back independently without coordinating releases across the stack.
* **Graceful Degradation & Partial Success:** `switchboard-room` orchestrates downstream calls with strict per-hop timeouts so a slow or faulted downstream subsystem degrades only its specific telemetry or readout rather than failing the entire operator action. For example, if `chime-regulator` fails to index a span snapshot, the state update still completes and surfaces a degraded-readout flag to the console.
* **Sane, Non-Cascading Retries:** Only idempotent diagnostic operations (`PROBE`, trace history reads) perform at most one bounded retry with jitter on transient transport errors. State-mutating actions (`CALIBRATE`, `ENGAGE`, `RESET`) never auto-retry blindly, preventing retry amplification against cold-starting instances or Redis rate limits.
* **Health Probes & Zero-Secret Client Boundary:** Every service exposes a lightweight `/healthz` endpoint (verifying process readiness and, where applicable, non-blocking Redis connectivity) for container lifecycle checks. Players access the hosted game with zero API keys, `.env` files, or third-party logins.

### Infrastructure & Services
* **Frontend:** Vintage naval/maritime CRT hardware-console SPA hosted on Cloudflare Pages (permanent physical switchboard controls + toggleable monochrome CRT readout screen).
* **Backend Microservices (Python 3.12+ / FastAPI on Cloud Run, Tier 1 region):**
  * `switchboard-room` — Public gateway (mapped to `clocktower.littlefuzzydinos.com/api` behind Cloudflare), session orchestrator, and move-history outline representing the operator's electrical relay console.
  * `mainspring-drive` — Private service; supplies primary rotational power, stage state, exhibit schematics, and warm/cold Redis cache lookups.
  * `escapement-gear` — Private service; mechanical timing regulator, puzzle validator, and physical consequence delay engine (`asyncio.sleep`).
  * `chime-regulator` — Private service; strike-counting mechanism that indexes lightweight span snapshots in Upstash Redis for the in-game Span Inspector.
* **Service-to-Service Security:** Downstream services (`mainspring-drive`, `escapement-gear`, `chime-regulator`) are deployed with `--no-allow-unauthenticated` (`roles/run.invoker` granted exclusively to `switchboard-room`'s service account). `switchboard-room` attaches Google-signed OIDC ID tokens in hosted environments (`ENV=prod`).
* **Observability Stack (OpenTelemetry, VictoriaMetrics & Grafana):**
  * **Telemetry Emission:** All four FastAPI services emit vendor-agnostic OTLP/HTTP (`https://collector.littlefuzzydinos.com/v1/traces`) and call `provider.forceFlush()` synchronously before returning each HTTP response so scale-to-zero containers never drop or throttle spans on shutdown.
  * **Metrics & Dashboards:** The GCP `e2-micro` OTel Collector derives RED metrics (rate, errors, duration) via `span_metrics` into **VictoriaMetrics**, visualized in **Grafana** alongside trace data for operational visibility across cold starts, stage completion rates, and downstream latency.
  * **In-Game Span Inspector:** Powered directly by `chime-regulator` and Upstash Redis—rendering real trace waterfalls immediately in the browser without querying external backends or exposing credentials.

### Monorepo Layout
* `/apps/web` — Vite + React + TypeScript vintage maritime-CRT console SPA (Cloudflare Pages).
* `/services/switchboard-room` — FastAPI gateway & session orchestrator.
* `/services/mainspring-drive` — FastAPI power source, stage state & cache state.
* `/services/escapement-gear` — FastAPI timing regulator, puzzle validator & delay engine.
* `/services/chime-regulator` — FastAPI strike log & trace snapshot indexer.
* `/packages/otel-contracts` — Shared JSON/YAML semantic convention definitions (`stage.*`, `mechanism.*`, `cache.*`, `circuit_breaker.*`).

### Local Execution & Testing
* **Environment Switching (`ENV=local` vs `ENV=prod`):** In `ENV=local`, `switchboard-room` skips attaching Google OIDC ID tokens and routes to local service ports over plain HTTP, keeping application business logic identical across environments.
* **Isolated Unit Tests:** Per-service unit tests (`pytest` + `httpx.AsyncClient`) run completely offline with zero external dependencies—using `fakeredis` (`FakeAsyncRedis`) for in-memory Redis state and TTL simulation, and OpenTelemetry's in-memory span exporter for trace assertions.
* **Local Integration Tests:** Cross-service integration tests run against local service processes and a local Redis instance to verify multi-service orchestration, graceful partial degradation, and contract compatibility without hitting any cloud endpoints or live telemetry collectors.
* **CI Integration Verification:** Cloud-backed end-to-end integration tests run exclusively inside GitHub Actions CI workflows, never during local test execution.

---

## Console UI & Controls Specification

* **Fixed Console Layout:** The physical switchboard console stays identical across all stages, with no pre-listed stage roadmap or stage-switcher menu, so new stages can be added or reordered without UI rewrites.
* **Single Non-Interactive CRT Screen:** One CRT display with zero on-screen clicking, toggled via a physical view switch between:
  * **Chamber View:** Displays the current stage status, copyable `session.id`, operational briefing text, and active subsystem target status.
  * **Trace View (Span Inspector):** Displays the live waterfall of the last 5 traces in the session, span durations, structured attributes, span events, and side-by-side latency comparison.
* **Three Physical Analog Gauges with Engraved Plaques:** Mounted on the console casing, each identified by a clear engraved metal plaque (`MAINS TENSION`, `RESONANCE DRAG`, `RESERVE PRESSURE`). Their dial faces are weathered and unlabelled so exact numbers cannot be read directly, while their needles react dynamically to real backend state:
  * **`MAINS TENSION`:** Tracks active mechanical load and torque buildup—surging during cold-start wake-up, indicating relative subsystem load, and climbing into the danger stop when a safety circuit breaker trips.
  * **`RESONANCE DRAG`:** Reacts to processing delay and synchronization stability—oscillating widely when timing is out of tune and settling steady as latency drops.
  * **`RESERVE PRESSURE`:** Tracks stored energy and decay over time—rising when state is pressurized in Redis and drifting downward in real time as TTLs expire.
* **Hardware Navigation & Inspection Controls:**
  * **View Toggle Switch:** Physical switch that flips the single CRT screen between Chamber View and Trace View.
  * **Side Navigation & Inspection Buttons (`PREV` / `NEXT` + `SELECT` / `EXPAND`):** Pressing `PREV` / `NEXT` triggers a temporary pop-up selection menu overlay on the CRT screen that highlights available subsystem targets or trace items as you scroll through them and fades out automatically once selected; `SELECT` / `EXPAND` drills into or expands trace waterfalls and span details on Trace View.
  * **Notched Calibration Slider (`0–100`, step `5`):** Tactile 21-position physical slider (`0, 5, 10 ... 100`) that sets the numeric parameter for the active subsystem target.
  * **4 Fixed Action Switches:**
    * `PROBE` — Fires a read-only diagnostic pulse across the microservices to observe latency, cold-start behavior, and current span attributes without mutating settings.
    * `CALIBRATE` — Applies the current notched slider value to the selected target in Redis and emits a calibration trace.
    * `ENGAGE` — Executes the mechanism check to verify whether the stage's conditions are satisfied; solves and advances on success, or reveals the stalled/faulted span in telemetry.
    * `RESET` — Clears session puzzle state and vents tripped circuit-breaker fault states back to baseline in Redis, emitting a reset trace.

### Engineer's Field Manual (Educational & Instructional Overlay)
To keep the CRT Trace Screen strictly diegetic while teaching real-world observability concepts, all game instructions, hints, and architecture notes live in an external **Engineer's Field Manual** paired alongside the switchboard:

* **Three Structured Tabs (Driven by `stage_id`):**
  * **How to Play:** Explains the physical switchboard controls (`PROBE`, `CALIBRATE`, `ENGAGE`, `RESET`, the `0–100` notched slider, `PREV`/`NEXT` target selector, and toggling between Chamber View and Trace View).
  * **Stage Hints:** Progressive, stage-specific diagnostic nudges pointing players toward relevant span attributes, waterfall delays, or analog gauge reactions without revealing exact target values.
  * **Real-World Parallel:** Explains the underlying distributed-systems failure mode modeled by the current stage (e.g., scale-to-zero container cold starts, tail latency, staggered Redis TTL expiration, silent configuration drift, and cascading backpressure) along with a post-stage wrap-up.
* **Automatic Stage Transitions:**
  * Entering a new stage automatically brings the **Field Manual** into primary focus so the player reads the stage briefing and real-world scenario first.
  * Clearing a stage (`ENGAGE` succeeds) automatically returns focus to the **Field Manual** to display the stage's real-world takeaway before advancing.
* **Responsive Focus-Swap Behavior:**
  * **Desktop (Side-by-Side Split-Focus):** Both the Switchboard Console and Field Manual remain visible side by side and swap scale when clicked (or via `ESC` / `Focus Panel`). When the Field Manual is in focus, it expands to primary reading size while the Switchboard Console scales back off to the side with live gauges still visible; clicking the console restores full-size controls while tucking the Field Manual to the side as a compact reference card.
  * **Mobile / Narrow Viewports (Full-Screen Stack + Peek Bar):** The active view fills ~85–90% of the viewport while the inactive view docks to the top or bottom edge as a slim tap bar (showing either the active stage title + `FIELD MANUAL` toggle when solving, or live mini gauge readouts + `FOCUS PANEL` button when reading).

---

## 4. Stage Specifications (Stages 1–5)

### Stage Summary Matrix

| Stage | Name | Diagnostic Mechanic | Key Telemetry Artifact | Primary Controls Used |
| :--- | :--- | :--- | :--- | :--- |
| **01** | Wake the Tower | Cold-start vs. warm latency comparison | Duration waterfall comparison | `PROBE`, `CALIBRATE`, `ENGAGE` |
| **02** | Resonance Tuning | Child-span latency bottleneck isolation | Child-span duration spikes | `PROBE`, `CALIBRATE` |
| **03** | Cache Warmth & TTL | Cache invalidation & TTL expiration timing | `cache.hit`, `cache.ttl_remaining_ms` | Multi-target `CALIBRATE` + `ENGAGE` |
| **04** | Hidden Attributes | Structured attribute & event inspection | `mechanism.nominal_load`, Events | Trace Inspector detail view |
| **05** | Cascading Backpressure | Circuit breakers & error state recovery | `span.status = ERROR`, Breaker event | `CALIBRATE`, `RESET` |

## Stage Specifications

### Stage 1: Wake the Tower
* **Objective:** Wake the dormant downstream clockwork services from a cold state and verify all subsystems are responsive before engaging the tower.
* **Mechanics & Telemetry:**
  * All downstream Cloud Run services (`mainspring-drive`, `escapement-gear`, and `chime-regulator`) begin dormant (scaled to zero).
  * Pressing `PROBE` dispatches an initial request across the microservices, capturing cold-start boot latency and setting `container.cold_start = true` on newly initialized spans.
  * Inspecting the trace waterfall in Trace View reveals which subsystem incurred the heaviest boot delay and confirms warm responsiveness on subsequent probes.
  * Pressing `ENGAGE` succeeds once all three downstream services respond within warm baseline thresholds.
* **Analog Gauge Behavior:**
  * **`MAINS TENSION`:** Sits flat at zero while containers are asleep, jumps sharply when `PROBE` wakes the services, and settles into a steady idle band once all three respond.
  * **`RESONANCE DRAG`:** Pegs high during the initial cold-start `PROBE` while the slowest service boots up, then drops down to a low, steady reading on subsequent warm probes.
  * **`RESERVE PRESSURE`:** Rises from zero up to a baseline idle level once the downstream containers are warm and holding active state.

### Stage 2: Resonance Tuning
* **Objective:** Tune the escapement mechanism to its hidden resonant notch by minimizing span processing latency.
* **Mechanics & Telemetry:**
  * `escapement-gear` introduces a synthetic latency penalty (`asyncio.sleep`) proportional to the distance between its calibrated slider value (`0–100`, step `5`) and a hidden target resonant frequency.
  * Players run `PROBE` to inspect the `escapement-gear` span duration on Trace View, adjust the notched slider, apply changes with `CALIBRATE`, and compare consecutive trace waterfalls side by side.
  * Pressing `ENGAGE` succeeds once `escapement-gear` span latency drops below `< 200ms`.
* **Analog Gauge Behavior:**
  * **`MAINS TENSION`:** Tracks the slider's current notch position on `escapement-gear`, rising or falling directly as new calibration values are dialed in.
  * **`RESONANCE DRAG`:** Oscillates widely when `escapement-gear` is out of tune (mirroring the synthetic latency drag), settling down into a calm, steady low band as calibration approaches the resonant notch.
  * **`RESERVE PRESSURE`:** Holds steady at its normal baseline idle reading throughout tuning.

### Stage 3: Cache Warmth & TTL Decay
* **Objective:** Pressurize all three pneumatic reserve barrels simultaneously before their staggered Redis cache TTLs expire.
* **Mechanics & Telemetry:**
  * Each subsystem (`mainspring-drive`, `escapement-gear`, and `chime-regulator`) relies on an ephemeral Redis key with a staggered TTL (`30s`, `20s`, and `15s` respectively).
  * Selecting a barrel and pressing `CALIBRATE` writes its pressurized state to Redis and records `cache.hit = true` alongside `cache.ttl_remaining_ms` in the span attributes.
  * If any key expires before `ENGAGE` is flipped, that service falls back to a cache miss (`cache.hit = false`) and fails the check, requiring the player to sequence calibrations from longest TTL to shortest TTL.
* **Analog Gauge Behavior:**
  * **`RESERVE PRESSURE`:** Jumps upward each time a barrel is pressurized with `CALIBRATE` (reflecting combined active charge) and visibly drifts downward in real time as the Redis TTLs count down and expire.
  * **`MAINS TENSION`:** Steps up as each barrel comes online under pressure and drops back a notch whenever an individual barrel's Redis key expires.
  * **`RESONANCE DRAG`:** Stays low when hitting warm Redis keys, spiking briefly whenever a barrel expires and triggers a cold state reload.

### Stage 4: Hidden Span Attributes
* **Objective:** Balance three clockwork counterweights whose target values are omitted from the Chamber Screen and exposed only inside structured OpenTelemetry span attributes.
* **Mechanics & Telemetry:**
  * `mainspring-drive`, `escapement-gear`, and `chime-regulator` start out of balance, with zero target numbers displayed on the Chamber Screen.
  * Firing `PROBE` and expanding each child span on Trace View reveals custom attributes: `gear.nominal_load`, `gear.current_load`, and `gear.delta`.
  * Players select each subsystem, dial the notched slider to match `gear.nominal_load`, and save with `CALIBRATE` until `gear.delta == 0` across all three services before pressing `ENGAGE`.
* **Analog Gauge Behavior:**
  * **`MAINS TENSION`:** Deflects proportionally to the currently selected subsystem's true nominal load (`gear.nominal_load`)—offering a relative physical hint of magnitude while keeping exact notch values hidden in the telemetry.
  * **`RESONANCE DRAG`:** Vibrates proportionally to the total imbalance (`gear.delta`) across the three counterweights, settling down to zero vibration once all three match their nominal loads.
  * **`RESERVE PRESSURE`:** Holds steady at its normal baseline idle reading throughout calibration.

### Stage 5: Cascading Backpressure & Circuit Breakers
* **Objective:** Achieve sufficient combined torque across all three subsystems without tripping the safety pawl circuit breaker.
* **Mechanics & Telemetry:**
  * `mainspring-drive`, `escapement-gear`, and `chime-regulator` must produce a combined torque output `>= 120` without exceeding the safety pawl's structural ceiling of `<= 150`.
  * Pushing combined torque above `150` during `CALIBRATE` or `ENGAGE` trips the safety pawl circuit breaker on `chime-regulator`, marking `span.status = ERROR`, recording a `breaker.tripped` span event, and rejecting downstream work until cleared.
  * Once tripped, the player must flip `RESET` to bleed off the fault state in Redis before re-calibrating within the `120–150` safe operating window and pressing `ENGAGE`.
* **Analog Gauge Behavior:**
  * **`MAINS TENSION`:** Climbs steadily toward a weathered red danger zone on the dial as combined torque approaches `150`, then snaps hard past the stop and stays pinned there once the circuit breaker trips until `RESET` clears the fault.
  * **`RESONANCE DRAG`:** Shudders violently when total torque enters the overload zone above `150`, then drops flat to zero while the tripped circuit breaker blocks downstream work.
  * **`RESERVE PRESSURE`:** Builds under load as torque increases, then vents sharply down to zero the instant the safety pawl breaker trips.

---

## API Contracts (Gateway: `switchboard-room`)
* `POST /api/session` — Creates or resumes an anonymous `session.id`, returning the active stage briefing, available subsystem targets, and initial analog gauge states (`MAINS TENSION`, `RESONANCE DRAG`, `RESERVE PRESSURE`).
* `POST /api/action` — Accepts `{ session_id, stage_id, action: "PROBE" | "CALIBRATE" | "ENGAGE" | "RESET", target, value }`, orchestrates downstream calls, flushes OTel spans, and returns updated stage state, updated analog gauge readings, and the latest trace snapshot (with `gauge.*` attributes stripped).
* `GET /api/traces/{session_id}` — Returns the last 5 indexed trace waterfalls from `chime-regulator` (with `gauge.*` attributes stripped) for inspection and comparison in Trace View.

---

## Phased Rollout
* **Phase 1 (Initial Production Release):** Ship the full physical console UI, core backend services, OTel telemetry pipeline, and **Stage 1** deployed and playable in production.
* **Phase 2 (Incremental Stage Rollout):** Deploy **Stages 2–5** incrementally behind the same fixed console layout without requiring any frontend control changes.
* **Phase 3 (Honeycomb Expansion):** Standalone optional extension adding direct-to-Honeycomb OTLP export and hidden `gauge.*` telemetry across all stages (detailed in the Honeycomb Expansion section).

---

## Honeycomb v3 Expansion

### Direct-to-Honeycomb Export & Telemetry Filtering
* **Direct OTLP Export (Bypasses Hosted Collector):** When `HONEYCOMB_API_KEY` (and optional `HONEYCOMB_DATASET`) are set in the local `.env`, the FastAPI microservices configure their OpenTelemetry `OTLPSpanExporter` to send OTLP/HTTP traces directly to `https://api.honeycomb.io/v1/traces`. This completely bypasses the hosted OpenTelemetry Collector pipeline while leaving the in-browser span ring buffer untouched.
* **In-Browser Attribute Stripping:** Before rendering spans on the Trace Screen, the backend strips out all `gauge.*` attributes. The three weathered physical gauges remain purely visual cues in the console UI, while their exact numeric readings and diagnostic fields are exposed exclusively in Honeycomb.

### Stage-by-Stage Honeycomb Telemetry & Visualizations

#### Stage 1: Wake the Tower
* **Extra Honeycomb Attributes:** `gauge.mains_tension.raw`, `gauge.resonance_drag.spike_ms`, and container initialization phase timings.
* **What You See in Honeycomb:** Heatmaps and BubbleUp across repeated `PROBE` runs isolate scale-to-zero cold-start outliers (`container.cold_start = true`) from warm steady-state requests, showing how a single slow downstream container boot drags out an entire parent request waterfall.

#### Stage 2: Resonance Tuning
* **Extra Honeycomb Attributes:** `gauge.resonance_drag.oscillation_hz` and `escapement.detune_delta`.
* **What You See in Honeycomb:** Plotting `escapement.detune_delta` against `duration_ms` across calibration attempts reveals the full tail-latency curve of a misconfigured service parameter (such as a bad polling interval or thread-pool setting) rather than comparing two traces one by one.

#### Stage 3: Cache Warmth & TTL Decay
* **Extra Honeycomb Attributes:** `gauge.reserve_pressure.psi` and `cache.expires_at_epoch_ms`.
* **What You See in Honeycomb:** Time-series queries over `gauge.reserve_pressure.psi` visualize the live sawtooth charge-and-decay cycle across all three Redis keys simultaneously, pinpointing race conditions where an upstream cache TTL expires before dependent downstream work finishes.

#### Stage 4: Hidden Span Attributes
* **Extra Honeycomb Attributes:** `gauge.mains_tension.deflection_deg` and `gauge.resonance_drag.jitter_index`.
* **What You See in Honeycomb:** High-cardinality `GROUP BY` queries correlate the unlabelled physical needle angles directly to `gear.nominal_load` and `gear.delta`, demonstrating how structured span metadata catches silent configuration drift that `200 OK` status codes and aggregate dashboards miss.

#### Stage 5: Cascading Backpressure & Circuit Breakers
* **Extra Honeycomb Attributes:** `gauge.mains_tension.overload_pct` and `breaker.state` (`CLOSED` vs. `TRIPPED`).
* **What You See in Honeycomb:** Service Maps and Honeycomb Triggers track cascading backpressure propagating into `chime-regulator`, alert when `gauge.mains_tension.overload_pct > 100`, and verify clean load-shedding recovery once the breaker is reset.
