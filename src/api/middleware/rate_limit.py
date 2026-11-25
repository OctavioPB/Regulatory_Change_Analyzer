"""Simple in-memory sliding-window rate limiter for ingestion endpoints."""
import time
from collections import deque

from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

_INGEST_PREFIX = "/api/v1/ingest"
_RATE_LIMITED_METHODS = {"POST"}

_BODY_429 = b'{"detail":"Rate limit exceeded. Try again later."}'


class IngestRateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter applied only to POST /api/v1/ingest/* requests."""

    def __init__(self, app: ASGIApp, max_requests: int = 10, window_seconds: int = 60) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next):
        if (
            request.method in _RATE_LIMITED_METHODS
            and request.url.path.startswith(_INGEST_PREFIX)
        ):
            client_ip: str = request.client.host if request.client else "unknown"
            now = time.monotonic()
            window_start = now - self._window

            # Drop buckets that have fully expired so memory doesn't grow per-IP forever
            for ip in [ip for ip, b in self._buckets.items() if not b or b[-1] < window_start]:
                del self._buckets[ip]

            bucket = self._buckets.setdefault(client_ip, deque())
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= self._max:
                return Response(
                    content=_BODY_429,
                    status_code=429,
                    media_type="application/json",
                    headers={"Retry-After": str(self._window)},
                )
            bucket.append(now)

        return await call_next(request)
