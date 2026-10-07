import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .db import make_engine, make_sessionmaker
from .errors import APIError, error_response
from .routers import alerts, auth, bulk, consumptions, projects, reports, resources, roles, tasks
from .validation import validation_message

logger = logging.getLogger('pulso')


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title='Pulso API',
        version='0.2.0',
        docs_url='/api/docs',
        redoc_url=None,
        openapi_url='/api/openapi.json',
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    for module in (auth, projects, tasks, consumptions, reports, resources, roles, alerts, bulk):
        app.include_router(module.router)

    @app.middleware('http')
    async def limits_and_headers(request: Request, call_next):
        length = request.headers.get('content-length', '')
        upload = request.url.path.startswith('/api/carga-masiva/')
        # Multipart framing adds a little to the file itself; the router enforces the exact file size.
        limit = settings.max_upload_bytes + 64 * 1024 if upload else settings.max_body_bytes
        shown = settings.max_upload_bytes if upload else settings.max_body_bytes
        if length.isdigit() and int(length) > limit:
            response = error_response(
                413, 'http_413', f'La solicitud supera el tamaño máximo de {shown // (1024 * 1024)} MiB.'
            )
        else:
            response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.url.path.startswith('/api/') and request.url.path != '/api/docs':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(APIError)
    async def api_error(_: Request, error: APIError):
        return error_response(error.status, error.code, str(error))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError):
        errors = error.errors()
        if errors and errors[0]['loc'][0] == 'path':  # e.g. /api/roles/abc, like Flask's <int:> routes
            return error_response(404, 'http_404', 'No se encontró el registro.')
        return error_response(400, 'validation_error', validation_message(errors[0] if errors else {}))

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, __: IntegrityError):
        return error_response(
            409,
            'conflict',
            'No se puede completar: el nombre ya existe o el registro tiene referencias asociadas.',
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, error: StarletteHTTPException):
        message = 'Error interno del servidor.' if error.status_code >= 500 else str(error.detail)
        return error_response(error.status_code, f'http_{error.status_code}', message)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, error: Exception):
        logger.exception('Error no controlado', exc_info=error)
        return error_response(500, 'http_500', 'Error interno del servidor.')

    @app.get('/api/health', tags=['sistema'])
    def health() -> dict[str, str]:
        with app.state.engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status': 'ok'}

    return app
