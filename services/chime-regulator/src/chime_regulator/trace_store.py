"""Redis-backed rolling trace waterfall store (max 5 newest traces per session)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Protocol, cast

import redis.asyncio as redis_async
from redis.exceptions import RedisError

from chime_regulator.models import TraceWaterfall

logger = logging.getLogger(__name__)


class TraceStore(Protocol):
    """Storage interface for per-session rolling trace waterfalls."""

    async def append_trace(self, session_id: str, waterfall: TraceWaterfall) -> bool:
        """Index a new trace waterfall newest-first. Returns True on success, False on failure."""
        ...

    async def get_traces(self, session_id: str) -> list[TraceWaterfall]:
        """Return up to the 5 most recent trace waterfalls (newest-first)."""
        ...


class RedisTraceStore:
    """redis.asyncio trace store keeping up to 5 newest TraceWaterfalls per session."""

    def __init__(
        self,
        client: redis_async.Redis,
        max_traces: int = 5,
        ttl_seconds: int = 3600,
    ) -> None:
        self._client = client
        self._max_traces = max_traces
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(session_id: str) -> str:
        return f"clocktower:traces:{session_id}"

    async def append_trace(self, session_id: str, waterfall: TraceWaterfall) -> bool:
        """Push waterfall to the head of the session list, trim to max_traces, and set TTL."""
        key = self._key(session_id)
        payload = waterfall.model_dump_json()
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.lpush(key, payload)
                pipe.ltrim(key, 0, self._max_traces - 1)
                pipe.expire(key, self._ttl_seconds)
                await pipe.execute()
            return True
        except (RedisError, OSError):
            logger.warning(
                "Failed to index trace waterfall in Redis for session %s",
                session_id,
                exc_info=True,
            )
            return False

    async def get_traces(self, session_id: str) -> list[TraceWaterfall]:
        """Retrieve up to max_traces waterfalls newest-first; degrade gracefully on Redis error."""
        key = self._key(session_id)
        try:
            raw_items = await cast(
                Awaitable[list[bytes | str]],
                self._client.lrange(key, 0, self._max_traces - 1),
            )
        except (RedisError, OSError):
            logger.warning(
                "Failed to read trace waterfalls from Redis for session %s",
                session_id,
                exc_info=True,
            )
            return []

        waterfalls: list[TraceWaterfall] = []
        for raw in raw_items:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            waterfalls.append(TraceWaterfall.model_validate_json(text))
        return waterfalls
