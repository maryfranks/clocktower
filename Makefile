.PHONY: help all check test \
	frontend frontend-lint frontend-typecheck frontend-test frontend-build \
	switchboard switchboard-lint switchboard-format switchboard-format-check switchboard-typecheck switchboard-test \
	chime chime-regulator chime-regulator-lint chime-regulator-format chime-regulator-format-check chime-regulator-typecheck chime-regulator-test

WEB_DIR := app/web
SWITCHBOARD_DIR := services/switchboard-room
CHIME_DIR := services/chime-regulator

help:
	@echo "Available targets:"
	@echo "  make all              Run lint, typecheck, and tests for all services"
	@echo "  make frontend         Run lint, typecheck, and tests for app/web"
	@echo "  make switchboard      Run lint, format check, typecheck, and tests for switchboard-room"
	@echo "  make chime-regulator  Run lint, format check, typecheck, and tests for chime-regulator (alias: chime)"
	@echo ""
	@echo "Granular targets:"
	@echo "  frontend-{lint,typecheck,test,build}"
	@echo "  switchboard-{lint,format,format-check,typecheck,test}"
	@echo "  chime-regulator-{lint,format,format-check,typecheck,test}"

all: frontend switchboard chime-regulator
check: all
test: all

# --- Frontend (app/web) ---
frontend: frontend-lint frontend-typecheck frontend-test

frontend-lint:
	bun run --cwd $(WEB_DIR) lint

frontend-typecheck:
	bun run --cwd $(WEB_DIR) tsc --noEmit

frontend-test:
	bun run --cwd $(WEB_DIR) test

frontend-build:
	bun run --cwd $(WEB_DIR) build

# --- Switchboard Room (services/switchboard-room) ---
switchboard: switchboard-lint switchboard-format-check switchboard-typecheck switchboard-test

switchboard-lint:
	uv run --directory $(SWITCHBOARD_DIR) ruff check .

switchboard-format:
	uv run --directory $(SWITCHBOARD_DIR) ruff format .

switchboard-format-check:
	uv run --directory $(SWITCHBOARD_DIR) ruff format --check .

switchboard-typecheck:
	uv run --directory $(SWITCHBOARD_DIR) mypy src tests

switchboard-test:
	uv run --directory $(SWITCHBOARD_DIR) pytest

# --- Chime Regulator (services/chime-regulator) ---
chime: chime-regulator
chime-regulator: chime-regulator-lint chime-regulator-format-check chime-regulator-typecheck chime-regulator-test

chime-regulator-lint:
	uv run --directory $(CHIME_DIR) ruff check .

chime-regulator-format:
	uv run --directory $(CHIME_DIR) ruff format .

chime-regulator-format-check:
	uv run --directory $(CHIME_DIR) ruff format --check .

chime-regulator-typecheck:
	uv run --directory $(CHIME_DIR) mypy src tests

chime-regulator-test:
	uv run --directory $(CHIME_DIR) pytest
