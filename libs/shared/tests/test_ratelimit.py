import pytest

from shared.ratelimit import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


def test_allows_up_to_limit(clock):
    lim = SlidingWindowLimiter(clock=clock)
    for _ in range(3):
        assert lim.hit("k", max_requests=3, window_seconds=60) is None
    assert lim.hit("k", max_requests=3, window_seconds=60) is not None


def test_retry_after_counts_down_as_time_passes(clock):
    lim = SlidingWindowLimiter(clock=clock)
    for _ in range(2):
        lim.hit("k", max_requests=2, window_seconds=60)
    assert lim.hit("k", max_requests=2, window_seconds=60) == pytest.approx(60)
    clock.now += 45
    assert lim.hit("k", max_requests=2, window_seconds=60) == pytest.approx(15)


def test_window_slides_and_frees_capacity(clock):
    lim = SlidingWindowLimiter(clock=clock)
    for _ in range(2):
        lim.hit("k", max_requests=2, window_seconds=60)
    clock.now += 61
    assert lim.hit("k", max_requests=2, window_seconds=60) is None


def test_rejected_hits_are_not_recorded(clock):
    """A limited client hammering the endpoint must not push its own
    retry time further into the future."""
    lim = SlidingWindowLimiter(clock=clock)
    for _ in range(2):
        lim.hit("k", max_requests=2, window_seconds=60)
    for _ in range(10):
        lim.hit("k", max_requests=2, window_seconds=60)  # all rejected
    clock.now += 61
    assert lim.hit("k", max_requests=2, window_seconds=60) is None


def test_keys_are_independent(clock):
    lim = SlidingWindowLimiter(clock=clock)
    for _ in range(2):
        lim.hit("a", max_requests=2, window_seconds=60)
    assert lim.hit("a", max_requests=2, window_seconds=60) is not None
    assert lim.hit("b", max_requests=2, window_seconds=60) is None


def test_reset_clears_all_state(clock):
    lim = SlidingWindowLimiter(clock=clock)
    for _ in range(2):
        lim.hit("k", max_requests=2, window_seconds=60)
    lim.reset()
    assert lim.hit("k", max_requests=2, window_seconds=60) is None
