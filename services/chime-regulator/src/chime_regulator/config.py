"""Environment configuration for chime-regulator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Environment = Literal["local", "prod"]


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    env: Environment = "local"
    redis_url: str = "redis://localhost:6379/0"
    trace_history_limit: int = 5
    trace_ttl_seconds: int = 3600
    otel_service_name: str = "chime-regulator"
    otel_exporter_otlp_endpoint: str | None = None
    honeycomb_api_key: str | None = None


def load_settings() -> Settings:
    """Load service settings from process environment variables."""
    raw_env = os.getenv("ENV", "local").strip().lower()
    env: Environment = "prod" if raw_env == "prod" else "local"

    return Settings(
        env=env,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        trace_history_limit=int(os.getenv("TRACE_HISTORY_LIMIT", "5")),
        trace_ttl_seconds=int(os.getenv("TRACE_TTL_SECONDS", "3600")),
        otel_service_name=os.getenv("OTEL_SERVICE_NAME", "chime-regulator"),
        otel_exporter_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None,
        honeycomb_api_key=os.getenv("HONEYCOMB_API_KEY") or None,
    )
