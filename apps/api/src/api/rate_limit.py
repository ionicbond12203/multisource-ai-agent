"""
Request limits for the public demo.

The free Gemini tier allows 15 model calls a minute for the whole app, and a
question takes up to 3. Without limits, one visitor clicking quickly can use
the quota up for everyone, including the interviewer trying the demo.

Counters live in memory, which is right for a single server process (the
free Render instance). Behind several processes they would need a shared
store such as Redis.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from api.config import Settings

MINUTE = 60.0
HOUR = 60 * MINUTE
DAY = 24 * HOUR


class SlidingWindow:
    """Allows at most `limit` hits per key in any `window` seconds. A limit of 0 means no limit."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}

    def retry_after(self, key: str) -> float | None:
        """Seconds until `key` may hit again, or None if it may now."""
        if self.limit <= 0:
            return None
        hits = self._prune(key)
        if len(hits) < self.limit:
            return None
        return max(hits[0] + self.window - self.clock(), 0.0)

    def hit(self, key: str) -> None:
        if self.limit > 0:
            self._prune(key).append(self.clock())

    def _prune(self, key: str) -> deque[float]:
        hits = self._hits.setdefault(key, deque())
        cutoff = self.clock() - self.window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if not hits and len(self._hits) > 10_000:
            # Keep memory bounded when many different visitors come by.
            self._hits = {k: v for k, v in self._hits.items() if v}
            hits = self._hits.setdefault(key, deque())
        return hits


@dataclass(frozen=True)
class Rule:
    window: SlidingWindow
    per_client: bool  # False: one shared counter for the whole app
    message: str  # "{seconds}" is replaced with the wait


class RateLimiter:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules
        self._lock = threading.Lock()

    def check(self, client: str) -> None:
        """Counts one request, or raises HTTP 429 without counting it if any rule is over its limit."""
        with self._lock:
            for rule in self.rules:
                key = client if rule.per_client else "*"
                wait = rule.window.retry_after(key)
                if wait is not None:
                    seconds = max(math.ceil(wait), 1)
                    raise HTTPException(
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        rule.message.format(seconds=seconds, when=_when(seconds)),
                        headers={"Retry-After": str(seconds)},
                    )
            for rule in self.rules:
                rule.window.hit(client if rule.per_client else "*")


@dataclass(frozen=True)
class Limits:
    chat: RateLimiter
    uploads: RateLimiter


def build_limits(settings: Settings, clock: Callable[[], float] = time.monotonic) -> Limits:
    chat = RateLimiter(
        [
            Rule(
                SlidingWindow(settings.chat_per_client_per_minute, MINUTE, clock),
                per_client=True,
                message="You're asking faster than this free demo allows. Try again {when}.",
            ),
            Rule(
                SlidingWindow(settings.chat_per_client_per_day, DAY, clock),
                per_client=True,
                message="You've reached today's question limit for this demo. Try again {when}.",
            ),
            Rule(
                SlidingWindow(settings.chat_per_minute, MINUTE, clock),
                per_client=False,
                message="The demo is busy right now (free AI quota). Try again {when}.",
            ),
        ]
    )
    uploads = RateLimiter(
        [
            Rule(
                SlidingWindow(settings.uploads_per_client_per_hour, HOUR, clock),
                per_client=True,
                message="Upload limit reached for this demo. Try again {when}.",
            )
        ]
    )
    return Limits(chat=chat, uploads=uploads)


def client_key(request: Request) -> str:
    """
    The visitor's IP address. Behind a proxy (Render) it is the first entry of
    X-Forwarded-For. A visitor can fake that header to dodge the per-visitor
    limits, but not the app-wide limit, which is what protects the quota.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


def _when(seconds: int) -> str:
    if seconds < 90:
        return f"in {seconds} seconds"
    if seconds < 2 * 3600:
        return f"in {math.ceil(seconds / 60)} minutes"
    return f"in {math.ceil(seconds / 3600)} hours"
