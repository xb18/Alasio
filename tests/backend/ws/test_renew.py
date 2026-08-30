"""
Unit tests for RenewalCodeManager.

Pure in-memory module: no filesystem / logger mock needed. The clock is
injectable, so the 20s ttl is tested with a fake clock instead of real
waiting; gc() returns the number of removed codes for assertions.
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from alasio.backend.ws.renew import RenewalCodeManager, RenewalLimitExceeded


class FakeClock:
    """Injectable monotonic clock for RenewalCodeManager tests."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestIssue:
    def test_format_and_recorded(self):
        """issue() returns a 64-hex code that is recorded in the table."""
        manager = RenewalCodeManager(clock=FakeClock())
        code = manager.issue()
        assert re.fullmatch(r'[0-9a-f]{64}', code)
        assert code in manager._codes

    def test_uniqueness(self):
        """Many consecutive issues never repeat."""
        manager = RenewalCodeManager(clock=FakeClock())
        codes = {manager.issue() for _ in range(100)}
        assert len(codes) == 100

    def test_capacity_limit(self):
        """issue() refuses beyond max_codes."""
        manager = RenewalCodeManager(clock=FakeClock(), max_codes=2)
        manager.issue()
        manager.issue()
        with pytest.raises(RenewalLimitExceeded):
            manager.issue()

    def test_issue_after_gc_recovers_capacity(self):
        """A full table recovers after gc() removes expired codes."""
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock, max_codes=2)
        manager.issue()
        manager.issue()
        # expire both codes and gc them, then issue works again
        clock.advance(21)
        removed = manager.gc()
        assert removed == 2
        code = manager.issue()
        assert code is not None


class TestRedeem:
    def test_success_consumes_code(self):
        """A valid code redeems True and is consumed (second redeem False)."""
        manager = RenewalCodeManager(clock=FakeClock())
        code = manager.issue()
        assert manager.redeem(code) is True
        assert manager.redeem(code) is False

    def test_unknown_code_false(self):
        manager = RenewalCodeManager(clock=FakeClock())
        assert manager.redeem('deadbeef') is False

    @pytest.mark.parametrize("elapsed, expected", [
        (0.0, True),
        (19.9, True),
        (20.0, True),
        (20.1, False),
    ])
    def test_expiry_boundary(self, elapsed, expected):
        """A code expires only when now - issued > ttl (== ttl is valid)."""
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock, ttl=20.0)
        code = manager.issue()
        clock.advance(elapsed)
        assert manager.redeem(code) is expected

    def test_expired_code_consumed(self):
        """An expired code is still consumed (pop happens first)."""
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock)
        code = manager.issue()
        clock.advance(30)
        assert manager.redeem(code) is False
        # the code is gone even though the redeem failed
        assert code not in manager._codes


class TestGc:
    def test_partial_expiry(self):
        """gc() removes only expired codes and returns the count."""
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock)
        code_a = manager.issue()  # at t=0
        clock.advance(4)
        code_b = manager.issue()  # at t=4
        clock.advance(10)
        code_c = manager.issue()  # at t=14
        clock.advance(11)  # now t=25: a (25) and b (21) expired, c (11) valid
        removed = manager.gc()
        assert removed == 2
        assert code_a not in manager._codes
        assert code_b not in manager._codes
        assert code_c in manager._codes

    def test_empty_table_noop(self):
        manager = RenewalCodeManager(clock=FakeClock())
        assert manager.gc() == 0

    def test_none_expired_noop(self):
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock)
        manager.issue()
        clock.advance(10)
        assert manager.gc() == 0

    def test_gc_restores_capacity(self):
        """gc() frees slots so issue() works again on a full table."""
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock, max_codes=2)
        manager.issue()
        manager.issue()
        with pytest.raises(RenewalLimitExceeded):
            manager.issue()
        clock.advance(30)
        manager.gc()
        assert manager.issue() is not None


class TestConcurrency:
    def test_concurrent_issue_redeem(self):
        """Concurrent issue + redeem: no exception, no duplicate codes."""
        manager = RenewalCodeManager(clock=FakeClock())
        errors = []

        def worker(_):
            try:
                code = manager.issue()
                assert manager.redeem(code) is True
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(64)))
        assert not errors
        # every issued code was redeemed, the table is empty
        assert len(manager._codes) == 0

    def test_concurrent_redeem_same_code_once(self):
        """Concurrent redeem of the same code: exactly one True."""
        manager = RenewalCodeManager(clock=FakeClock())
        code = manager.issue()
        results = []
        lock = threading.Lock()

        def worker(_):
            ok = manager.redeem(code)
            with lock:
                results.append(ok)

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(worker, range(16)))
        assert results.count(True) == 1
        assert results.count(False) == 15

    def test_concurrent_gc_with_issue_redeem(self):
        """gc() concurrent with issue/redeem: no exception, table consistent."""
        clock = FakeClock()
        manager = RenewalCodeManager(clock=clock)
        errors = []

        # issue codes, let them all expire, then run gc concurrently
        # with more issue/redeem traffic (previously gc() iterated the
        # dict without the lock and could hit RuntimeError while another
        # thread resized it)
        for _ in range(50):
            manager.issue()
        clock.advance(30)

        def worker(n):
            try:
                if n % 2 == 0:
                    manager.gc()
                else:
                    code = manager.issue()
                    manager.redeem(code)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(worker, range(64)))
        assert not errors
        # expired codes were gc'd; the remaining ones are fresh (unexpired)
        assert all(clock.t - issued <= 20 for issued in manager._codes.values())
        # every remaining code is redeemable exactly once
        for code in list(manager._codes):
            assert manager.redeem(code) is True
