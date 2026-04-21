from backend.app.rate_limit import build_adaptive_rate_limit_headers


class _DummyLimitItem:
    amount = 5

    def get_expiry(self) -> int:
        return 60


class _DummyLimiterBackend:
    def __init__(
        self,
        reset_epoch: float,
        remaining: int,
        should_fail: bool = False,
    ) -> None:
        self.reset_epoch = reset_epoch
        self.remaining = remaining
        self.should_fail = should_fail

    def get_window_stats(self, _limit_item, *_scope_args):
        if self.should_fail:
            raise RuntimeError("storage unavailable")
        return self.reset_epoch, self.remaining


class _DummyLimiter:
    def __init__(self, backend: _DummyLimiterBackend) -> None:
        self.limiter = backend


def test_build_adaptive_headers_with_remaining_budget():
    current_limit = (_DummyLimitItem(), ["127.0.0.1", "claims"])
    limiter = _DummyLimiter(_DummyLimiterBackend(reset_epoch=130.0, remaining=2))

    headers = build_adaptive_rate_limit_headers(
        limiter,
        current_limit,
        now_epoch=100.0,
    )

    assert headers["RateLimit-Limit"] == "5"
    assert headers["RateLimit-Remaining"] == "2"
    assert headers["RateLimit-Reset"] == "30"
    assert headers["RateLimit-Policy"] == "5;w=60"
    assert "Retry-After" not in headers


def test_build_adaptive_headers_adds_retry_after_when_exhausted():
    current_limit = (_DummyLimitItem(), ["127.0.0.1", "claims"])
    limiter = _DummyLimiter(_DummyLimiterBackend(reset_epoch=118.0, remaining=0))

    headers = build_adaptive_rate_limit_headers(
        limiter,
        current_limit,
        now_epoch=100.0,
    )

    assert headers["RateLimit-Remaining"] == "0"
    assert headers["RateLimit-Reset"] == "18"
    assert headers["Retry-After"] == "18"


def test_build_adaptive_headers_returns_empty_when_unavailable():
    assert build_adaptive_rate_limit_headers(_DummyLimiter(_DummyLimiterBackend(100.0, 1)), None) == {}

    current_limit = (_DummyLimitItem(), ["127.0.0.1", "claims"])
    limiter = _DummyLimiter(
        _DummyLimiterBackend(
            reset_epoch=110.0,
            remaining=1,
            should_fail=True,
        )
    )

    assert build_adaptive_rate_limit_headers(limiter, current_limit, now_epoch=100.0) == {}
