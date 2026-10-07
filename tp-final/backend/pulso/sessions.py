"""Server-side sessions, CSRF and the request guard applied to every API router.

Guard order (same as the Flask version): 401 unauthorized -> 403 password_change_required
-> 400 csrf_invalid -> 415 non-JSON body -> 400 body must be a JSON object.
`json_body=False` skips the 415 and body checks (multipart uploads).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import get_db
from .errors import APIError, forbidden
from .models import Recurso, Sesion
from .security import new_token, same_token, token_hash

COOKIE = 'pulso_session'
ANONYMOUS_TTL = timedelta(hours=2)
MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}

DB = Annotated[Session, Depends(get_db)]


@dataclass
class RequestSession:
    row: Sesion | None
    user: Recurso | None


def load_session(request: Request, db: DB) -> RequestSession:
    token = request.cookies.get(COOKIE)
    row = db.get(Sesion, token_hash(token)) if token else None
    if row is None or row.expira <= datetime.now(UTC):
        return RequestSession(None, None)
    user = db.get(Recurso, row.recurso_id) if row.recurso_id else None
    return RequestSession(row, user)


State = Annotated[RequestSession, Depends(load_session)]


def guard(require_user: bool = True, allow_pending: bool = False, json_body: bool = True):
    async def dependency(request: Request, state: State) -> None:
        if require_user:
            if state.user is None:
                raise APIError('Iniciá sesión para continuar.', 401, 'unauthorized')
            if state.user.debe_cambiar_password and not allow_pending:
                raise APIError('Debés cambiar tu contraseña inicial.', 403, 'password_change_required')
        if request.method not in MUTATING:
            return
        token = request.headers.get('X-CSRF-Token', '')
        if state.row is None or not same_token(token, state.row.csrf):
            raise APIError('La sesión del formulario venció. Recargá la página.', 400, 'csrf_invalid')
        if not json_body:  # multipart uploads: auth and CSRF only
            return
        content_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
        if content_type != 'application/json':
            raise APIError('Enviá un cuerpo JSON con Content-Type: application/json.', 415, 'http_415')
        try:
            body = await request.json()
        except ValueError:
            raise APIError('El cuerpo JSON no es válido.', 400, 'validation_error') from None
        if not isinstance(body, dict):
            raise APIError('El cuerpo JSON debe ser un objeto.', 400, 'validation_error')

    return dependency


protected = [Depends(guard())]


def current_user(state: State) -> Recurso:
    if state.user is None:  # The guard already rejected this; kept as a safety net.
        raise APIError('Iniciá sesión para continuar.', 401, 'unauthorized')
    return state.user


User = Annotated[Recurso, Depends(current_user)]


def require_admin(user: User) -> Recurso:
    if not user.es_admin:
        raise forbidden('Esta acción requiere permisos de administrador.')
    return user


def start_session(db: Session, response: Response, request: Request, user: Recurso | None) -> Sesion:
    """Replace the caller's session with a fresh token (new CSRF too) and set the cookie."""
    settings = request.app.state.settings
    now = datetime.now(UTC)
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(Sesion).where(Sesion.token_hash == token_hash(old)))
    db.execute(delete(Sesion).where(Sesion.expira <= now))  # opportunistic cleanup
    token = new_token()
    ttl = timedelta(days=settings.session_days) if user else ANONYMOUS_TTL
    row = Sesion(
        token_hash=token_hash(token),
        recurso_id=user.recurso_id if user else None,
        csrf=new_token(),
        expira=now + ttl,
    )
    db.add(row)
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite='lax',
        secure=settings.cookie_secure,
        path='/',
    )
    return row
