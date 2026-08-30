"""
Tests for alasio.backend.app.create_config.

Focus: the hypercorn SSL wiring. hypercorn Config uses `keyfile` /
`certfile` field names (not uvicorn-style `ssl_keyfile` /
`ssl_certfile`); assigning the wrong names would silently create plain
instance attributes and leave the port plaintext.
"""

from alasio.backend.app import create_config


class FakeBackend:
    def __init__(self, ssl):
        self.Host = ''
        self.Port = 0
        self.WebuiSSLKey = '/path/key.pem' if ssl else None
        self.WebuiSSLCert = '/path/cert.pem' if ssl else None


class FakeDeployData:
    def __init__(self, ssl):
        self.Backend = FakeBackend(ssl)
        # create_config reads `DeployConfig().config.data`
        self.data = self


class FakeDeployConfig:
    def __init__(self, ssl):
        self.config = FakeDeployData(ssl)


class TestCreateConfig:
    def test_ssl_sets_hypercorn_keyfile_certfile(self, monkeypatch):
        """SSL configured: hypercorn must be given keyfile/certfile."""
        monkeypatch.setattr(
            'alasio.backend.app.apply_hypercorn_exclusivity_patch', lambda: None)
        monkeypatch.setattr('alasio.ext.env.set_project_root', lambda root: None)
        monkeypatch.setattr(
            'alasio.deploy.config.model.DeployConfig',
            lambda: FakeDeployConfig(ssl=True),
        )

        config = create_config([])

        # the field names hypercorn actually reads
        assert config.keyfile == '/path/key.pem'
        assert config.certfile == '/path/cert.pem'
        assert config.ssl_enabled

    def test_no_ssl_leaves_plaintext(self, monkeypatch):
        """No SSL configured: hypercorn stays plaintext."""
        monkeypatch.setattr(
            'alasio.backend.app.apply_hypercorn_exclusivity_patch', lambda: None)
        monkeypatch.setattr('alasio.ext.env.set_project_root', lambda root: None)
        monkeypatch.setattr(
            'alasio.deploy.config.model.DeployConfig',
            lambda: FakeDeployConfig(ssl=False),
        )

        config = create_config([])

        assert config.keyfile is None
        assert config.certfile is None
        assert not config.ssl_enabled
