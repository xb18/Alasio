import jwt
from starlette import status
from starlette.requests import Request

from alasio.backend.mpipe.token_backend import token_table
from alasio.ext.starapi.param import HTTPExceptionJson


async def require_electron(request: Request):
    """
    Electron-layer dependency: the request must carry a valid
    X-Alasio-Token (injected by the Electron main process webRequest;
    verified against the backend token table). Orthogonal to
    require_login: this checks the electron token only, not the JWT.

    Args:
        request (Request):

    Raises:
        HTTPExceptionJson: 403 when the token is missing or invalid
    """
    if not token_table.verify_header(request):
        raise HTTPExceptionJson(
            status_code=status.HTTP_403_FORBIDDEN,
            err='AUTH_ELECTRON_ONLY',
        )


async def require_login(request: Request):
    """
    Login-layer dependency: the request must carry a valid JWT in the
    alasio_token cookie. Orthogonal to require_electron: this checks the
    JWT only, not the electron token.

    Args:
        request (Request):

    Raises:
        HTTPExceptionJson: 401 when the JWT cookie is missing or invalid
    """
    from alasio.backend.auth.auth import JWT_MANAGER

    token = request.cookies.get('alasio_token', '')
    try:
        JWT_MANAGER.validate_token(token)
    except jwt.PyJWTError:
        raise HTTPExceptionJson(
            status_code=status.HTTP_401_UNAUTHORIZED,
            err='AUTH_TOKEN_INVALID',
            headers={'WWW-Authenticate': 'Bearer'},
        ) from None
