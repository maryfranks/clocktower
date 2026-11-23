"""Environment configuration for switchboard-room."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Environment = Literal["local", "prod"]
DownstreamMode = Literal["mock", "http"]


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    env: Environment = "local"
    chime_regulator_url: str = "http://localhost:8001"
    chime_regulator_mode: DownstreamMode = "http"
    otel_service_name: str = "switchboard-room"
    otel_exporter_otlp_endpoint: str | None = None
    honeycomb_api_key: str | None = None
    downstream_timeout_seconds: float = 5.0


def load_settings() -> Settings:
    """Load service settings from process environment variables."""
    raw_env = os.getenv("ENV", "local").strip().lower()
    env: Environment = "prod" if raw_env == "prod" else "local"

    raw_mode = os.getenv("CHIME_REGULATOR_MODE", "http").strip().lower()
    mode: DownstreamMode = "mock" if raw_mode == "mock" else "http"

    timeout_raw = os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "5.0")
    return Settings(
        env=env,
        chime_regulator_url=os.getenv("CHIME_REGULATOR_URL", "http://localhost:8001").rstrip("/"),
        chime_regulator_mode=mode,
        otel_service_name=os.getenv("OTEL_SERVICE_NAME", "switchboard-room"),
        otel_exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
        honeycomb_api_key=os.getenv("HONEYCOMB_API_KEY") or None,
        downstream_timeout_seconds=float(timeout_raw),
    )
