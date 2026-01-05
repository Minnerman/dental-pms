from __future__ import annotations

import time
from collections import defaultdict, deque


class SimpleRateLimiter:
    def __init__(self, *, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        events = self._events[key]
        while events and events[0] < window_start:
            events.popleft()
        if len(events) >= self.max_events:
            return False
        events.append(now)
        return True
