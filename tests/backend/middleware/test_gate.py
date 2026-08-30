"""
Tests for DeploymentGateMiddleware (merged admission + login gate).

The middleware is the single web entrance: rule A (no password -> only
electron token passes), rule B (lan mode -> lan sources only) and the
login layer (JWT cookie) run inside one middleware in a fixed order
(admission first, then login). It must never be split or reordered.
"""

import pytest

from alasio.backend.auth.auth import JWT_MANAGER
from alasio.backend.middleware.gate import DeploymentGateMiddleware
from alasio.backend.mpipe.token_backend import token_table


class CaptureApp:
    """Records whether the inner app was reached."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})


def make_scope(scope_type, path='/api/test', host='127.0.0.1', headers=None):
    """
    Build a minimal ASGI scope.

    Args:
        scope_type (str): 'http' or 'websocket'
        path (str):
        host (str): The TCP peer address
        headers (list): Raw header pairs

    Returns:
        Scope:
    """
    return {
        'type': scope_type,
        'method': 'GET',
        'path': path,
        'headers': headers or [],
        'client': (host, 12345),
        'query_string': b'',
        'scheme': 'http',
        'server': ('127.0.0.1', 22267),
    }


def make_http_scope(**kwargs):
    return make_scope('http', **kwargs)


def make_ws_scope(**kwargs):
    return make_scope('websocket', **kwargs)


async def call_gate(mw, scope):
    """
    Run the middleware against a scope and collect the sent messages.

    Args:
        mw (DeploymentGateMiddleware):
        scope (Scope):

    Returns:
        list: The messages sent through `send`
    """
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    await mw(scope, receive, send)
    return sent


def status_of(sent):
    """
    Args:
        sent (list): Messages sent by the middleware

    Returns:
        int | None: The http response status, or None if none was sent
    """
    for message in sent:
        if message['type'] == 'http.response.start':
            return message['status']
    return None


def ws_closed(sent):
    """
    Args:
        sent (list): Messages sent by the middleware

    Returns:
        int | None: The websocket close code, or None if not closed
    """
    for message in sent:
        if message['type'] == 'websocket.close':
            return message['code']
    return None


class FakeBackend:
    def __init__(self, ssl):
        self.WebuiSSLCert = 'cert.pem' if ssl else ''
        self.WebuiSSLKey = 'key.pem' if ssl else ''


class FakeDeployData:
    def __init__(self, ssl):
        self.Backend = FakeBackend(ssl)


@pytest.fixture(autouse=True)
def reset_token_table():
    """The token table is a module-level singleton; clear it per test."""
    yield
    token_table._tokens.clear()


@pytest.fixture(autouse=True)
def auth_env(monkeypatch):
    """Default: no password configured; tests override as needed."""
    monkeypatch.setattr(JWT_MANAGER, 'secret', b'test-secret')
    monkeypatch.setattr(JWT_MANAGER, 'pwd', '')
    yield
    monkeypatch.undo()


@pytest.fixture
def gate(monkeypatch):
    """Factory: build a middleware + CaptureApp pair with a fake deploy data."""

    def make(ssl=False):
        app = CaptureApp()
        mw = DeploymentGateMiddleware(app)
        monkeypatch.setattr(
            DeploymentGateMiddleware, '_deploy_data',
            staticmethod(lambda: FakeDeployData(ssl)),
        )
        return mw, app

    return make


def set_password(monkeypatch, pwd='secret'):
    monkeypatch.setattr(JWT_MANAGER, 'pwd', pwd)


def valid_cookie_header():
    token = JWT_MANAGER.create()
    return [(b'cookie', b'alasio_token=' + token.encode())]


class TestRuleA:
    """No password: only requests carrying a valid electron token pass."""

    @pytest.mark.trio
    async def test_http_without_token_403(self, gate):
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope())
        assert status_of(sent) == 403
        assert not app.called

    @pytest.mark.trio
    async def test_http_with_forged_token_403(self, gate):
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(headers=[(b'x-alasio-token', b'forged')]))
        assert status_of(sent) == 403
        assert not app.called

    @pytest.mark.trio
    async def test_http_with_valid_token_passes(self, gate):
        token_table.seed_from_supervisor(('tok1',))
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(headers=[(b'x-alasio-token', b'tok1')]))
        assert status_of(sent) == 200
        assert app.called

    @pytest.mark.trio
    async def test_static_resources_pass_without_token(self, gate):
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(path='/favicon.png'))
        assert status_of(sent) == 200
        assert app.called

    @pytest.mark.trio
    async def test_ws_without_token_rejected_4001(self, gate):
        mw, app = gate()
        sent = await call_gate(mw, make_ws_scope())
        assert ws_closed(sent) == 4001
        assert not app.called

    @pytest.mark.trio
    async def test_ws_with_valid_token_passes(self, gate):
        token_table.seed_from_supervisor(('tok1',))
        mw, app = gate()
        sent = await call_gate(mw, make_ws_scope(headers=[(b'x-alasio-token', b'tok1')]))
        assert ws_closed(sent) is None
        assert app.called


class TestRuleB:
    """Lan mode (no SSL): only lan sources pass."""

    # the exempt path skips the login layer so only the source check runs
    PATH = '/api/auth/renew'

    @pytest.mark.parametrize('host', [
        '127.0.0.1', '::1', '10.1.2.3', '172.16.0.1', '172.31.255.255',
        '192.168.1.5', '169.254.1.1', 'fe80::1', 'fd00::1',
    ])
    @pytest.mark.trio
    async def test_lan_sources_allowed(self, gate, monkeypatch, host):
        set_password(monkeypatch)
        mw, app = gate()
        await call_gate(mw, make_http_scope(path=self.PATH, host=host))
        assert app.called

    @pytest.mark.parametrize('host', [
        '8.8.8.8', '100.64.0.1', '2001:db8::1', '203.0.113.5',
    ])
    @pytest.mark.trio
    async def test_public_sources_rejected(self, gate, monkeypatch, host):
        set_password(monkeypatch)
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(path=self.PATH, host=host))
        assert status_of(sent) == 403
        assert not app.called

    @pytest.mark.trio
    async def test_public_mode_skips_source_check(self, gate, monkeypatch):
        set_password(monkeypatch)
        mw, app = gate(ssl=True)
        await call_gate(mw, make_http_scope(path=self.PATH, host='8.8.8.8'))
        assert app.called

    @pytest.mark.trio
    async def test_unknown_host_refused(self, gate, monkeypatch):
        set_password(monkeypatch)
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(path=self.PATH, host='not-an-ip'))
        assert status_of(sent) == 403
        assert not app.called


class TestLoginLayer:
    """Login layer (JWT cookie) on /api http routes."""

    @pytest.mark.trio
    async def test_no_jwt_401(self, gate, monkeypatch):
        set_password(monkeypatch)
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope())
        assert status_of(sent) == 401
        assert not app.called

    @pytest.mark.trio
    async def test_invalid_jwt_401(self, gate, monkeypatch):
        set_password(monkeypatch)
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(headers=[(b'cookie', b'alasio_token=not-a-jwt')]))
        assert status_of(sent) == 401
        assert not app.called

    @pytest.mark.trio
    async def test_valid_jwt_passes(self, gate, monkeypatch):
        set_password(monkeypatch)
        mw, app = gate()
        await call_gate(mw, make_http_scope(headers=valid_cookie_header()))
        assert app.called

    @pytest.mark.trio
    async def test_exempt_endpoints_skip_login(self, gate, monkeypatch):
        set_password(monkeypatch)
        mw, app = gate()
        # no JWT cookie, but /api/auth/login performs the auth itself
        await call_gate(mw, make_http_scope(path='/api/auth/login'))
        assert app.called

    @pytest.mark.trio
    async def test_ws_scope_not_login_gated(self, gate, monkeypatch):
        # the ws handshake validates the JWT inside serve() so it can
        # close(4001) after accept; the middleware must pass it through
        set_password(monkeypatch)
        mw, app = gate()
        sent = await call_gate(mw, make_ws_scope())
        assert ws_closed(sent) is None
        assert app.called


class TestRuleOrder:
    """Admission rules run before the login layer (403 beats 401)."""

    @pytest.mark.trio
    async def test_no_password_no_token_is_403_not_401(self, gate):
        # default fixture: no password -> rule A rejects before the
        # login layer would answer 401
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope())
        assert status_of(sent) == 403
        assert not app.called

    @pytest.mark.trio
    async def test_rule_b_runs_before_login(self, gate, monkeypatch):
        # public source + valid jwt: rule B rejects with 403, the login
        # layer never runs (a valid jwt would have passed it)
        set_password(monkeypatch)
        mw, app = gate()
        sent = await call_gate(mw, make_http_scope(host='8.8.8.8', headers=valid_cookie_header()))
        assert status_of(sent) == 403
        assert not app.called


class TestNonHttpScope:
    """Non http/websocket scopes (lifespan) pass through."""

    @pytest.mark.trio
    async def test_lifespan_scope_passes(self, gate):
        mw, app = gate()
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {'type': 'lifespan.startup'}

        await mw({'type': 'lifespan'}, receive, send)
        assert app.called
