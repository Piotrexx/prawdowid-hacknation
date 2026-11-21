import time
from collections import deque


class RateLimiter:
    """Okno przesuwne w pamięci procesu. Przy wielu instancjach wymienić na Redis."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}

    def retry_after(self, key: str) -> int | None:
        """Rejestruje żądanie; zwraca liczbę sekund do odczekania, gdy limit jest przekroczony."""
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, int(self.window_s - (now - hits[0])) + 1)
        hits.append(now)
        if len(self._hits) > 10_000:
            self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] <= self.window_s}
        return None
