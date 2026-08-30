import jwt
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import Request


async def require_electron(request: Request):
    """
    Electron-layer dependency: the request must carry a valid
    X-Alasio-Token (injected by the Electron main process webRequest;
    verified against the backend token table). Orthogonal to
    require_login: this checks the electron token only, not the JWT.

    Args:
        request (Request):

    Raises:
        HTTPException: 403 when the token is missing or invalid
    """
    from alasio.backend.mpipe.token_backend import token_table

    if not token_table.verify_header(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='electron only')


async def require_login(request: Request):
    """
    Login-layer dependency: the request must carry a valid JWT in the
    alasio_token cookie. Orthogonal to require_electron: this checks the
    JWT only, not the electron token.

    Args:
        request (Request):

    Raises:
        HTTPException: 401 when the JWT cookie is missing or invalid
    """
    from alasio.backend.auth.auth import JWT_MANAGER

    token = request.cookies.get('alasio_token', '')
    try:
        JWT_MANAGER.validate_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            # detail must be quoted to become a valid json
            detail='"Token invalid or expired"',
            headers={'WWW-Authenticate': 'Bearer'},
        ) from None
