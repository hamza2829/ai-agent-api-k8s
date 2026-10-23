from collections import deque
import math
import threading
import time


class RateLimiter:
    """Sliding window, one process. Only valid credentials allocate a bucket."""
    def __init__(self, limit, window_seconds=60., clock=time.monotonic):
        if limit < 1 or not 0 < window_seconds <= 3600:
            raise ValueError('Invalid rate limit')
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self._buckets = {}
        self._lock = threading.Lock()

    def check(self, key):
        now = self.clock()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= now-self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False, max(1, math.ceil(self.window-(now-bucket[0])))
            bucket.append(now)
            return True, 0
