from agent_api.security import RateLimiter


def test_limiter_recovers_after_window_without_sleeping():
    now = [100.0]
    limiter = RateLimiter(limit=2, window_seconds=10.0, clock=lambda: now[0])
    assert limiter.check("key-a")[0] is True
    assert limiter.check("key-a")[0] is True
    allowed, retry_after = limiter.check("key-a")
    assert allowed is False
    assert retry_after >= 1
    now[0] += 10.01
    assert limiter.check("key-a")[0] is True


def test_limiter_does_not_share_quota_between_keys():
    limiter = RateLimiter(limit=1, window_seconds=60.0, clock=lambda: 10.0)
    assert limiter.check("key-a")[0] is True
    assert limiter.check("key-a")[0] is False
    assert limiter.check("key-b")[0] is True
