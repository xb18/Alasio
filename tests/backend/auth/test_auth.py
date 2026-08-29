import time

import jwt
import pytest

from alasio.backend.auth.auth import JwtManager

SECRET = b'test-secret-0123456789abcdef'
PASSWORD = 'test-password'


class TestValidateToken:
    """
    Tests for JwtManager.validate_token
    """

    def setup_method(self):
        self.jwt = JwtManager()
        # cached_property is a non-data descriptor, instance attribute assignment shadows it
        self.jwt.secret = SECRET
        self.jwt.pwd = PASSWORD

    def _make_token(self, sub=PASSWORD, iat=None, omit_iat=False, exp=3600, **extra):
        """
        Create a signed token for tests, mimicking JwtManager.create() which always
        includes exp. Pass sub=None to omit sub, omit_iat=True to omit iat, and
        exp=None to omit exp.

        Args:
            sub (str): Subject claim, None to omit
            iat (float): Issued-at timestamp, None means now
            omit_iat (bool): Omit the iat claim entirely
            exp (float): Expiry seconds from now, None to omit

        Returns:
            str: Signed JWT
        """
        now = int(time.time())
        data = {'sub': sub}
        if not omit_iat:
            data['iat'] = now if iat is None else iat
        if exp is not None:
            data['exp'] = now + exp
        data.update(extra)
        if sub is None:
            del data['sub']
        return jwt.encode(data, SECRET, algorithm=self.jwt.algorithm)

    def test_valid_token_keep_current(self):
        """Valid token issued within the renew window keeps the current token."""
        result = self.jwt.validate_token(self._make_token(iat=int(time.time())))
        assert result == ''

    def test_valid_token_renew(self):
        """Token older than renew_hours gets a renewed token."""
        iat = int(time.time()) - 2 * 3600
        result = self.jwt.validate_token(self._make_token(iat=iat))
        assert result != ''
        data = jwt.decode(result, SECRET, algorithms=[self.jwt.algorithm])
        assert data['sub'] == PASSWORD
        assert data['iat'] > iat

    def test_missing_exp(self):
        with pytest.raises(jwt.PyJWTError, match='Missing exp'):
            self.jwt.validate_token(self._make_token(exp=None))

    def test_missing_iat(self):
        with pytest.raises(jwt.PyJWTError, match='Missing iat'):
            self.jwt.validate_token(self._make_token(omit_iat=True))

    def test_missing_sub(self):
        """Missing sub raises 'Missing sub', not the copied 'Missing iat' message."""
        with pytest.raises(jwt.PyJWTError, match='Missing sub'):
            self.jwt.validate_token(self._make_token(sub=None))

    def test_password_mismatch(self):
        with pytest.raises(jwt.PyJWTError, match='Password incorrect'):
            self.jwt.validate_token(self._make_token(sub='wrong-password'))

    def test_invalid_token(self):
        with pytest.raises(jwt.PyJWTError):
            self.jwt.validate_token('not-a-jwt-token')

    def test_no_password_no_token_creates(self):
        """Without a configured password and without a token, a new token is created."""
        self.jwt.pwd = ''
        result = self.jwt.validate_token('')
        assert result != ''
        data = jwt.decode(result, SECRET, algorithms=[self.jwt.algorithm])
        assert data['sub'] == ''


class TestCreate:
    """
    Tests for JwtManager.create
    """

    def setup_method(self):
        self.jwt = JwtManager()
        self.jwt.secret = SECRET
        self.jwt.pwd = PASSWORD

    def test_create_payload(self):
        token = self.jwt.create()
        data = jwt.decode(token, SECRET, algorithms=['HS256'])
        assert data['sub'] == PASSWORD
        assert 'iat' in data
        assert 'exp' in data
        assert data['exp'] > data['iat']
