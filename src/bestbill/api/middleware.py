"""Pure-ASGI middleware: body limits, rate limiting, security headers and a
catch-all that never leaks internals. Nothing here reads or logs bodies.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)

_DOC_PATHS = ("/api/docs", "/api/redoc")

CSP_API = "default-src 'none'; frame-ancestors 'none'"
# Swagger UI loads its assets from a CDN and runs an inline bootstrap script.
CSP_DOCS = (
    "default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src data: https://fastapi.tiangolo.com; connect-src 'self'; "
    "frame-ancestors 'none'"
)


async def _send_json(
    send: Send,
    status: int,
    detail: str,
    *,
    extra: list[tuple[bytes, bytes]] | None = None,
) -> None:
    body = json.dumps({"detail": detail}, ensure_ascii=False).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        *(extra or []),
    ]
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class _BodyTooLarge(BaseException):  # noqa: N818
    """BaseException so framework ``except Exception`` blocks can't swallow it."""


class BodyLimitMiddleware:
    """Rejects request bodies over the per-path limit (413) before reading
    them all: by Content-Length up front, and by counting streamed chunks.
    """

    def __init__(
        self, app: ASGIApp, *, default_limit: int, path_limits: dict[str, int]
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.path_limits = path_limits

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.path_limits.get(scope["path"], self.default_limit)
        headers = dict(scope["headers"])
        declared = headers.get(b"content-length")
        message = "Richiesta troppo grande."
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = True
            if too_big:
                await _send_json(send, 413, message)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            msg = await receive()
            if msg["type"] == "http.request":
                received += len(msg.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return msg

        started = False

        async def tracking_send(msg: Message) -> None:
            nonlocal started
            if msg["type"] == "http.response.start":
                started = True
            await send(msg)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await _send_json(send, 413, message)


def client_ip(scope: Scope, trust_proxy: bool) -> str:
    if trust_proxy:
        for name, value in scope["headers"]:
            if name == b"x-forwarded-for":
                first: str = value.decode("latin-1").split(",")[0].strip()
                if first:
                    return first
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class RateLimitMiddleware:
    """Per-IP sliding-window limiter, in memory (one instance per process).

    ``/api/health`` is exempt (platform health checks). ``path_limits`` sets
    stricter per-minute limits for expensive paths.
    """

    MAX_KEYS = 10_000

    def __init__(
        self,
        app: ASGIApp,
        *,
        per_minute: int,
        path_limits: dict[str, int],
        trust_proxy: bool,
        window: float = 60.0,
    ) -> None:
        self.app = app
        self.per_minute = per_minute
        self.path_limits = path_limits
        self.trust_proxy = trust_proxy
        self.window = window
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def _allow(self, key: tuple[str, str], limit: int, now: float) -> float | None:
        """None if allowed, else seconds to wait."""
        if len(self._hits) > self.MAX_KEYS:
            self._hits.clear()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= limit:
            return self.window - (now - hits[0])
        hits.append(now)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or scope["method"] == "OPTIONS"
            or not path.startswith("/api/")
            or path == "/api/health"
        ):
            await self.app(scope, receive, send)
            return
        ip = client_ip(scope, self.trust_proxy)
        now = time.monotonic()
        checks = [(("all", ip), self.per_minute)]
        if path in self.path_limits:
            checks.append(((path, ip), self.path_limits[path]))
        for key, limit in checks:
            wait = self._allow(key, limit, now)
            if wait is not None:
                await _send_json(
                    send,
                    429,
                    "Troppe richieste: riprova tra poco.",
                    extra=[(b"retry-after", str(int(wait) + 1).encode())],
                )
                return
        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]
        csp = CSP_DOCS if path.startswith(_DOC_PATHS) else CSP_API
        extra = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"no-referrer"),
            (b"content-security-policy", csp.encode()),
        ]
        if scope["method"] == "POST":
            extra.append((b"cache-control", b"no-store"))

        async def send_with_headers(msg: Message) -> None:
            if msg["type"] == "http.response.start":
                present = {k.lower() for k, _ in msg["headers"]}
                msg["headers"] = [
                    *msg["headers"],
                    *((k, v) for k, v in extra if k not in present),
                ]
            await send(msg)

        await self.app(scope, receive, send_with_headers)


class CatchAllMiddleware:
    """Turns any unexpected exception into a generic 500. Logs only the
    exception type and route: never the message, traceback locals or body.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(msg: Message) -> None:
            nonlocal started
            if msg["type"] == "http.response.start":
                started = True
            await send(msg)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            log.error(
                "unhandled %s on %s %s",
                type(exc).__name__,
                scope["method"],
                scope["path"],
            )
            if not started:
                await _send_json(send, 500, "Errore interno. Riprova più tardi.")
