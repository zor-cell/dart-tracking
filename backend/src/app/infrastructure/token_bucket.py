"""In-process token bucket: how often something may happen, with room for a burst."""

import time


class TokenBucket:
    """Holds up to `burst` tokens and refills `rate` of them per second."""

    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._updated = time.monotonic()

    def take(self) -> bool:
        """Spend one token; False when none is left."""
        now = time.monotonic()
        self._tokens = min(self._burst, self._tokens + (now - self._updated) * self._rate)
        self._updated = now
        if self._tokens < 1:
            return False
        self._tokens -= 1
        return True
