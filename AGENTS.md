# Project Overview
The Clock Tower is a multi-service observability puzzle game built with four decoupled Python 3.15 (uv) FastAPI microservices (switchboard-room, chime-regulator, escapement-gear, pendulum-cache) and a Vite/React/TypeScript frontend (app/web/).

## Context & Global Baseline
Read ~/.agents/AGENTS.md as your global baseline configuration; repository-level rules in this file and .agents/rules/ take precedence wherever they conflict.

## Verification & Testing
- Run `uv run pytest` inside the modified `services/<name>/` directory before finishing any task.
- Validate all request/response payloads against `openapi.yaml`.
- Bug fixes must include a regression test reproducing the issue before the fix.
- Update `docs/architecture.md` or service docs in the same PR if endpoints, env vars, or state schemas change.
- For `app/web` use `bun run` for test, lint, etc. Use jsdom with @testing-library/react for UI component tests; never install or use real browser runners.

## Role Routing
Adopt the matching role before executing specialized tasks:
- Code and test implementation: ~/.agents/roles/engineer.md
- Documentation and spec maintenance: ~/.agents/roles/librarian.md
- Code and pull request review: ~/.agents/roles/reviewer.md

## Architectural Guardrails
- Never modify openapi.yaml unless explicitly instructed by a contract-change issue. Every service's request/response models must validate strictly against openapi.yaml.
- Never import Python modules or share packages across services/*. Each service owns its own pyproject.toml, uv.lock, src/, and tests/.
- switchboard-room must strip all gauge.* attributes from span payloads returned in API responses (GET /api/traces and POST /api/action) while preserving them on exported OpenTelemetry spans.
- Never execute tests/e2e/ locally; those tests run exclusively in GitHub Actions against live Cloud Run endpoints (CI=true).
- Read only the relevant stage or service section of docs/plan.md and docs/architecture.md for your active issue rather than loading unrelated sections.

## Documentation Index & Access Control

### Active Specifications (Agent Permitted)
- openapi.yaml: Single source of truth for all public and internal HTTP endpoints and schemas.
- docs/architecture.md: Service boundaries, request sequence flows, Redis TTL schema, and GCP/Cloudflare deployment topology.
- docs/plan.md: Game mechanics, stage puzzle rules, gauge formulas, and telemetry specifications (read targeted sections per issue).
- docs/design-system.md: frontend design specifications

### Human Only (Agents Do Not Read)
- README.md: Human-facing portfolio overview and local quickstart.
- services/*/README.md: Human-facing service operational cards (use openapi.yaml and docs/architecture.md instead).
