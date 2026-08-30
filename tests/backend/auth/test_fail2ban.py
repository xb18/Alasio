import time

import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.types import Scope

from alasio.backend.auth.fail2ban import Fail2Ban, Fail2BanManager, get_client_ip


@pytest.fixture(autouse=True)
def clear_singletons():
    """Fail2BanManager is a SingletonNamed; reset between tests."""
    yield
    Fail2BanManager.singleton_clear()


def make_scope(host='10.0.0.5', headers=None):
    """
    Build a minimal ASGI scope with a client address and headers.

    Args:
        host (str): The TCP peer address
        headers (list): Raw header pairs

    Returns:
        Scope:
    """
    scope: Scope = {
        'type': 'http',
        'method': 'POST',
        'path': '/api/auth/login',
        'headers': headers or [],
        'client': (host, 12345),
        'query_string': b'',
        'scheme': 'http',
        'server': ('127.0.0.1', 22267),
    }
    return scope


class TestGetClientIp:
    def test_uses_tcp_peer_ip(self):
        """Only request.client.host is trusted."""
        request = Request(make_scope(host='192.168.1.10'))
        assert get_client_ip(request) == '192.168.1.10'

    def test_ignores_xff_header(self):
        """X-Forwarded-For must never be read (spoofable)."""
        headers = [(b'x-forwarded-for', b'1.2.3.4'), (b'x-real-ip', b'5.6.7.8')]
        request = Request(make_scope(host='192.168.1.10', headers=headers))
        assert get_client_ip(request) == '192.168.1.10'

    def test_xff_forged_loopback_does_not_spoof(self):
        """X-Forwarded-For: 127.0.0.1 must not change the identity."""
        headers = [(b'x-forwarded-for', b'127.0.0.1')]
        request = Request(make_scope(host='10.0.0.9', headers=headers))
        assert get_client_ip(request) == '10.0.0.9'

    def test_no_client_falls_back_to_loopback(self):
        request = Request(make_scope(host=None))
        assert get_client_ip(request) == '127.0.0.1'


class TestCheckBan:
    def setup_method(self):
        self.ban = Fail2Ban('/login')
        self.ban.ip = '10.0.0.5'
        self.manager = Fail2BanManager('/login')

    def test_ban_does_not_extend_on_access(self):
        """Banned access must not extend the ban (removes the DoS path)."""
        end_time = time.time() + 60
        self.manager.banned_ips['10.0.0.5'] = end_time
        with pytest.raises(HTTPException) as excinfo:
            self.ban.check_ban()
        assert excinfo.value.status_code == 403
        # fixed duration: unchanged by the access
        assert self.manager.banned_ips['10.0.0.5'] == end_time

    def test_ban_expired_cleared(self):
        self.manager.banned_ips['10.0.0.5'] = time.time() - 1
        self.ban.check_ban()  # no exception
        assert '10.0.0.5' not in self.manager.banned_ips

    def test_not_banned_no_error(self):
        self.ban.check_ban()  # no exception

    def test_ban_response_after(self):
        """The 403 response is raised with the banned detail."""
        self.manager.banned_ips['10.0.0.5'] = time.time() + 30
        with pytest.raises(HTTPException) as excinfo:
            self.ban.check_ban()
        assert excinfo.value.status_code == 403


class TestRecordFailure:
    def setup_method(self):
        self.ban = Fail2Ban('/login')
        self.ban.ip = '10.0.0.5'
        self.manager = Fail2BanManager('/login')

    def test_five_failures_ban(self):
        """5 failures within the window ban the ip."""
        for i in range(4):
            error = self.ban.record_failure()
            assert error.status_code == 401
        error = self.ban.record_failure()
        assert error.status_code == 403
        assert '10.0.0.5' in self.manager.banned_ips

    def test_success_clears_failures(self):
        self.ban.record_failure()
        self.ban.record_failure()
        self.ban.record_success()
        assert '10.0.0.5' not in self.manager.failed_attempts

    def test_global_throttle_after_threshold(self):
        """More than global_threshold failures trigger the global cooldown."""
        manager = Fail2BanManager('/login')
        manager.global_threshold = 5
        # strictly more than the threshold (5) activates the cooldown
        for i in range(6):
            self.ban.record_failure()
        assert manager.global_blocked()

    def test_global_blocked_returns_429(self):
        """During the cooldown check_ban returns 429."""
        self.manager.global_cool_until = time.time() + 60
        with pytest.raises(HTTPException) as excinfo:
            self.ban.check_ban()
        assert excinfo.value.status_code == 429

    def test_global_failures_window_evicts_old(self):
        """Old failures outside the window are evicted."""
        now = time.time()
        manager = Fail2BanManager('/login')
        manager.global_failures = [now - 400, now]
        manager.record_global_failure()
        assert len(manager.global_failures) == 2
