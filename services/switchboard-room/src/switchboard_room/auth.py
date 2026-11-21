"""Service-to-service OIDC authentication for ENV=local and ENV=prod."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from switchboard_room.config import Environment


class AuthHeaderProvider(Protocol):
    """Provides outbound authentication headers for downstream HTTP calls."""

    def get_headers(self, audience: str) -> dict[str, str]:
        """Return HTTP headers required to call the target audience."""
        ...


class OidcAuthHeaderProvider:
    """Attaches Google-signed OIDC ID tokens in ENV=prod and skips them in ENV=local."""

    def __init__(
        self,
        env: Environment,
        token_fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self._env = env
        self._token_fetcher = token_fetcher or _fetch_google_id_token

    def get_headers(self, audience: str) -> dict[str, str]:
        """Return Authorization bearer header in prod, or empty dict locally."""
        if self._env != "prod":
            return {}
        token = self._token_fetcher(audience)
        return {"Authorization": f"Bearer {token}"}


def _fetch_google_id_token(audience: str) -> str:
    """Fetch a Google-signed OIDC ID token for the given Cloud Run audience."""
    fetcher = cast(Callable[[GoogleAuthRequest, str], str], id_token.fetch_id_token)
    return fetcher(GoogleAuthRequest(), audience)
